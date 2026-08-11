from base64 import b64encode
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.observer_model import TopicState
from topicgate.mcp.mcp_api import McpApi
from topicgate.mcp.models import TopicStateResult


class TopicAPI(McpApi):
    def __init__(self, runtime: TopicGateRuntime):
        self._runtime = runtime

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.list_topics)
        mcp.add_tool(self.get_topic_state)

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def list_topics(self) -> tuple[str, ...]:
        """List topics currently observed on the active broker profile."""
        return self._runtime.list_topics()

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_topic_state(
        self,
        broker_id: UUID,
        topic: str,
    ) -> TopicStateResult | None:
        """Get the latest observed state for a topic on a broker profile."""
        state = self._runtime.get_topic_state(broker_id, topic)
        return None if state is None else self._to_result(state)

    @staticmethod
    def _to_result(state: TopicState) -> TopicStateResult:
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
