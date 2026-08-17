from base64 import b64encode
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.mqtt_observation import MqttObservation
from topicgate.mcp.api.mcp_api import MCPApi
from topicgate.mcp.models import TopicStateResult


class TopicAPI(MCPApi):
    def __init__(
        self,
        runtime: TopicGateRuntime,
        resolver: BrokerResolver | None = None,
    ):
        self._runtime = runtime
        self._resolver = resolver or BrokerResolver(runtime)

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.list_topics)
        mcp.add_tool(self.get_topic_state)

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def list_topics(
        self,
        broker: UUID | str | None = None,
    ) -> tuple[str, ...]:
        """List observed topic names using the legacy read contract.

        Side effects: None; this does not activate, connect, or refresh a broker.
        Required state: Omit broker only when an active profile exists; results are
        limited to state already observed or restored during this process lifetime.
        Identifiers: broker accepts a UUID or unique case-insensitive name.
        Failures: Fails for no active profile or unknown or ambiguous profiles.
        """
        resolved = self._resolver.resolve_or_active(broker)
        return self._runtime.list_topics(resolved.id)

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_topic_state(
        self,
        broker_id: UUID | str,
        topic: str,
    ) -> TopicStateResult | None:
        """Read one observed topic using the legacy read contract.

        Side effects: None; this does not activate, connect, or refresh a broker.
        Required state: The profile must exist; an unobserved topic returns null.
        Identifiers: broker_id accepts a UUID or unique case-insensitive name;
        topic is an exact MQTT topic, not a wildcard filter.
        Failures: Fails for unknown or ambiguous profiles or state read errors.
        """
        resolved = self._resolver.resolve(broker_id)
        state = self._runtime.get_topic_state(resolved.id, topic)
        return None if state is None else self._to_result(state)

    @staticmethod
    def _to_result(state: MqttObservation) -> TopicStateResult:
        try:
            payload_text = state.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload_text = None
        return TopicStateResult(
            name=state.name,
            topic=state.topic,
            payload_text=payload_text,
            payload_base64=b64encode(state.payload).decode("ascii"),
            qos=state.qos,
            retain=state.retain,
            received_at=state.recieved_at,
            message_count=state.message_count,
            payload_size=state.payload_size or len(state.payload),
        )
