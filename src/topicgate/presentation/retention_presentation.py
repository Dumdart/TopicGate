from dataclasses import asdict, dataclass
from enum import StrEnum

from topicgate.core.models.observation_cache_administration import (
    BrokerCacheUsage,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)

MAX_SQLITE_INTEGER = (1 << 63) - 1


class ByteUnit(StrEnum):
    BYTES = "Bytes"
    KIB = "KiB"
    MIB = "MiB"
    GIB = "GiB"

    @property
    def multiplier(self) -> int:
        return {
            ByteUnit.BYTES: 1,
            ByteUnit.KIB: 1024,
            ByteUnit.MIB: 1024**2,
            ByteUnit.GIB: 1024**3,
        }[self]


class AgeUnit(StrEnum):
    SECONDS = "Seconds"
    MINUTES = "Minutes"
    HOURS = "Hours"
    DAYS = "Days"

    @property
    def multiplier(self) -> int:
        return {
            AgeUnit.SECONDS: 1,
            AgeUnit.MINUTES: 60,
            AgeUnit.HOURS: 3600,
            AgeUnit.DAYS: 86400,
        }[self]


@dataclass(frozen=True)
class RetentionPreset:
    name: str
    policy: ObservationRetentionPolicy


@dataclass(frozen=True)
class CacheUsageDisplay:
    usage: BrokerCacheUsage
    entry_utilization: float
    payload_utilization: float
    entry_warning: bool
    payload_warning: bool


RETENTION_PRESETS = (
    RetentionPreset(
        "Conservative",
        ObservationRetentionPolicy(
            max_entries_per_broker=250,
            max_entries_total=2_500,
            max_payload_bytes_per_topic=16 * 1024,
            max_payload_bytes_per_broker=2 * 1024**2,
            max_persisted_payload_database_bytes_total=64 * 1024**2,
            max_age_seconds=7 * 86400,
            warning_threshold=0.70,
            auto_remove_expired=True,
            auto_remove_excess=True,
            auto_remove_unsubscribed=True,
        ),
    ),
    RetentionPreset("Balanced", ObservationRetentionPolicy()),
    RetentionPreset(
        "Extended",
        ObservationRetentionPolicy(
            max_entries_per_broker=5_000,
            max_entries_total=50_000,
            max_payload_bytes_per_topic=256 * 1024,
            max_payload_bytes_per_broker=64 * 1024**2,
            max_persisted_payload_database_bytes_total=1024**3,
            max_age_seconds=90 * 86400,
            warning_threshold=0.90,
            auto_remove_expired=True,
            auto_remove_excess=True,
            auto_remove_unsubscribed=False,
        ),
    ),
)


def exact_byte_value(value: int, unit: ByteUnit) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Byte limit must be a positive integer.")
    result = value * unit.multiplier
    if result > MAX_SQLITE_INTEGER:
        raise ValueError("Byte limit exceeds SQLite integer capacity.")
    return result


def display_byte_value(value: int) -> tuple[int, ByteUnit]:
    for unit in reversed(tuple(ByteUnit)):
        if value % unit.multiplier == 0:
            return value // unit.multiplier, unit
    return value, ByteUnit.BYTES


def exact_age_seconds(value: int, unit: AgeUnit) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Maximum age must be positive or unlimited.")
    result = value * unit.multiplier
    if result > MAX_SQLITE_INTEGER:
        raise ValueError("Maximum age exceeds SQLite integer capacity.")
    return result


def display_age_value(value: int) -> tuple[int, AgeUnit]:
    for unit in reversed(tuple(AgeUnit)):
        if value % unit.multiplier == 0:
            return value // unit.multiplier, unit
    return value, AgeUnit.SECONDS


def validate_retention_policy_values(values: dict[str, object]) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        ObservationRetentionPolicy(**values)
    except (TypeError, ValueError):
        pass
    positive = (
        "max_entries_per_broker",
        "max_entries_total",
        "max_payload_bytes_per_topic",
        "max_payload_bytes_per_broker",
        "max_persisted_payload_database_bytes_total",
    )
    for name in positive:
        value = values.get(name)
        if type(value) is not int or value <= 0:
            errors[name] = "Enter a positive integer."
    threshold = values.get("warning_threshold")
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not 0 < threshold <= 1
    ):
        errors["warning_threshold"] = "Enter a percentage above 0 and at most 100."
    age = values.get("max_age_seconds")
    if age is not None and (type(age) is not int or age <= 0):
        errors["max_age_seconds"] = "Enter a positive age or choose Unlimited."
    if not errors.get("max_entries_per_broker") and not errors.get("max_entries_total"):
        if values["max_entries_per_broker"] > values["max_entries_total"]:
            errors["max_entries_per_broker"] = "Cannot exceed the total entry limit."
    payload_names = (
        "max_payload_bytes_per_topic",
        "max_payload_bytes_per_broker",
        "max_persisted_payload_database_bytes_total",
    )
    if not any(name in errors for name in payload_names):
        if values[payload_names[0]] > values[payload_names[1]]:
            errors[payload_names[0]] = "Cannot exceed the per-broker payload limit."
        if values[payload_names[1]] > values[payload_names[2]]:
            errors[payload_names[1]] = "Cannot exceed the database payload limit."
    return errors


def policy_values(policy: ObservationRetentionPolicy) -> dict[str, object]:
    return asdict(policy)


def cache_usage_display(
    usage: BrokerCacheUsage,
    policy: ObservationRetentionPolicy,
) -> CacheUsageDisplay:
    entries = usage.entry_count / policy.max_entries_per_broker
    payload = usage.stored_payload_bytes / policy.max_payload_bytes_per_broker
    return CacheUsageDisplay(
        usage,
        entries,
        payload,
        entries >= policy.warning_threshold,
        payload >= policy.warning_threshold,
    )
