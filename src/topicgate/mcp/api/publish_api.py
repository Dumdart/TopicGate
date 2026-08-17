from base64 import b64decode
from binascii import Error as Base64Error
from typing import Literal
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.mcp.api.mcp_api import MCPApi


class PublishAPI(MCPApi):
    def __init__(
        self,
        runtime: TopicGateRuntime,
        resolver: BrokerResolver | None = None,
    ):
        self._runtime = runtime
        self._resolver = resolver or BrokerResolver(runtime)

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.publish)

    @tool(
        annotations={
            "destructiveHint": True,
            "openWorldHint": True,
        }
    )
    async def publish(
        self,
        broker_id: UUID | str,
        topic: str,
        payload: str,
        payload_encoding: Literal["utf-8", "base64"] = "utf-8",
    ) -> None:
        """Publish a UTF-8 or base64-encoded payload to the active MQTT broker."""
        if payload_encoding == "base64":
            try:
                payload_bytes = b64decode(payload, validate=True)
            except (Base64Error, ValueError) as error:
                raise ValueError("The payload is not valid base64.") from error
        else:
            payload_bytes = payload.encode("utf-8")
        resolved = self._resolver.resolve(broker_id)
        await self._runtime.publish(resolved.id, topic, payload_bytes)
