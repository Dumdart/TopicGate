from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationRetentionPolicy:
    """Application-wide limits for persisted MQTT observations."""

    max_entries_per_broker: int = 1_000
    max_entries_total: int = 10_000
    warning_threshold: float = 0.80
    max_payload_bytes_per_topic: int = 64 * 1024
    max_payload_bytes_per_broker: int = 8 * 1024 * 1024
    max_persisted_payload_database_bytes_total: int = 256 * 1024 * 1024
    max_age_seconds: int | None = None
    auto_remove_expired: bool = True
    auto_remove_excess: bool = True
    auto_remove_unsubscribed: bool = False

    def __post_init__(self) -> None:
        positive_limits = {
            "max_entries_per_broker": self.max_entries_per_broker,
            "max_entries_total": self.max_entries_total,
            "max_payload_bytes_per_topic": self.max_payload_bytes_per_topic,
            "max_payload_bytes_per_broker": self.max_payload_bytes_per_broker,
            "max_persisted_payload_database_bytes_total": (
                self.max_persisted_payload_database_bytes_total
            ),
        }
        for name, value in positive_limits.items():
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if (
            not isinstance(self.warning_threshold, (int, float))
            or isinstance(self.warning_threshold, bool)
            or not 0 < self.warning_threshold <= 1
        ):
            raise ValueError("warning_threshold must be greater than 0 and at most 1.")
        if self.max_age_seconds is not None and (
            type(self.max_age_seconds) is not int or self.max_age_seconds <= 0
        ):
            raise ValueError("max_age_seconds must be a positive integer or None.")
        for name in (
            "auto_remove_expired",
            "auto_remove_excess",
            "auto_remove_unsubscribed",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean.")
        if self.max_entries_per_broker > self.max_entries_total:
            raise ValueError(
                "max_entries_per_broker cannot exceed max_entries_total."
            )
        if self.max_payload_bytes_per_topic > self.max_payload_bytes_per_broker:
            raise ValueError(
                "max_payload_bytes_per_topic cannot exceed "
                "max_payload_bytes_per_broker."
            )
        if (
            self.max_payload_bytes_per_broker
            > self.max_persisted_payload_database_bytes_total
        ):
            raise ValueError(
                "max_payload_bytes_per_broker cannot exceed "
                "max_persisted_payload_database_bytes_total."
            )
