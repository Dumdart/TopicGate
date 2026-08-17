from uuid import UUID

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.broker_summary import BrokerSummary


class BrokerNotFoundError(LookupError):
    """Raised when a broker selector does not match a configured broker."""


class AmbiguousBrokerError(ValueError):
    """Raised when a broker name matches more than one configured broker."""


class BrokerResolver:
    """Resolve broker summaries by UUID or case-insensitive profile name."""

    def __init__(self, runtime: TopicGateRuntime) -> None:
        self._runtime = runtime

    def resolve(self, selector: UUID | str) -> BrokerSummary:
        brokers = self._runtime.list_brokers()
        broker_id = self._parse_uuid(selector)
        if broker_id is not None:
            match = next((item for item in brokers if item.id == broker_id), None)
            if match is None:
                raise BrokerNotFoundError(f"Unknown broker UUID: {broker_id}")
            return match

        name = str(selector).strip()
        matches = tuple(
            item for item in brokers if item.name.casefold() == name.casefold()
        )
        if not matches:
            raise BrokerNotFoundError(f"Unknown broker name: {name!r}")
        if len(matches) > 1:
            matching_ids = ", ".join(str(item.id) for item in matches)
            raise AmbiguousBrokerError(
                f"Broker name {name!r} is ambiguous; matching UUIDs: {matching_ids}"
            )
        return matches[0]

    def resolve_or_active(
        self,
        selector: UUID | str | None,
    ) -> BrokerSummary:
        if selector is None:
            return self._runtime.active_broker
        return self.resolve(selector)

    @staticmethod
    def _parse_uuid(selector: UUID | str) -> UUID | None:
        if isinstance(selector, UUID):
            return selector
        try:
            return UUID(selector.strip())
        except (AttributeError, ValueError):
            return None
