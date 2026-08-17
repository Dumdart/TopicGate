from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from topicgate.app.services.broker_resolver import (
    AmbiguousBrokerError,
    BrokerNotFoundError,
    BrokerResolver,
)
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_summary import BrokerSummary


def broker(name: str) -> BrokerSummary:
    return BrokerSummary(
        id=uuid4(),
        name=name,
        config=MqttConfig("broker", 1883, "", ""),
        password_configured=False,
    )


def resolver_with(*brokers: BrokerSummary) -> BrokerResolver:
    runtime = MagicMock()
    runtime.list_brokers.return_value = brokers
    return BrokerResolver(runtime)


def test_resolver_finds_broker_by_uuid_object_or_string() -> None:
    expected = broker("Primary")
    resolver = resolver_with(expected)

    assert resolver.resolve(expected.id) is expected
    assert resolver.resolve(str(expected.id)) is expected


def test_resolver_matches_trimmed_name_case_insensitively() -> None:
    expected = broker("Living Room")

    resolved = resolver_with(expected).resolve("  living room  ")

    assert resolved is expected


def test_resolver_uses_active_broker_when_selector_is_omitted() -> None:
    expected = broker("Primary")
    runtime = MagicMock()
    runtime.active_broker = expected

    assert BrokerResolver(runtime).resolve_or_active(None) is expected
    runtime.list_brokers.assert_not_called()


def test_resolver_reports_unknown_uuid_without_treating_it_as_a_name() -> None:
    missing_id = uuid4()

    with pytest.raises(BrokerNotFoundError, match=str(missing_id)):
        resolver_with(broker(str(missing_id))).resolve(str(missing_id))


def test_resolver_reports_unknown_name_clearly() -> None:
    with pytest.raises(BrokerNotFoundError, match="Missing"):
        resolver_with(broker("Primary")).resolve("Missing")


def test_resolver_reports_all_ids_for_an_ambiguous_name() -> None:
    first = broker("Duplicate")
    second = broker("duplicate")

    with pytest.raises(AmbiguousBrokerError) as error:
        resolver_with(first, second).resolve("DUPLICATE")

    assert str(first.id) in str(error.value)
    assert str(second.id) in str(error.value)
