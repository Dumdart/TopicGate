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
        resolver: BrokerResolver,
    ):
        self._runtime = runtime
        self._resolver = resolver

    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        if control_enabled:
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
        payload_encoding: Literal["utf-8", "base64"],
    ) -> None:
        """Publish a UTF-8 or base64 payload to a selected MQTT broker.

        Side effects: Sends a message over MQTT and may affect external consumers.
        Required state: The selected broker must be active and connected.
        Identifiers: broker_id accepts a UUID or unique case-insensitive name;
        topic is an exact MQTT topic, not a wildcard subscription filter;
        payload_encoding must explicitly be utf-8 or base64.
        Failures: Fails for an invalid broker, encoding, topic, disconnected state,
        or MQTT publish error.
        """
        if payload_encoding == "base64":
            try:
                payload_bytes = b64decode(payload, validate=True)
            except (Base64Error, ValueError) as error:
                raise ValueError("The payload is not valid base64.") from error
        elif payload_encoding == "utf-8":
            payload_bytes = payload.encode("utf-8")
        else:
            raise ValueError(
                f"Unsupported payload encoding: {payload_encoding}"
            )
        resolved = self._resolver.resolve(broker_id)
        await self._runtime.publish(resolved.id, topic, payload_bytes)
