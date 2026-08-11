import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from topicgate.app.app_dependencies import AppDependencies
from topicgate.app.service_container import ServiceContainer
from topicgate.mcp.broker_api import BrokerAPI
from topicgate.mcp.connection_api import ConnectionAPI
from topicgate.mcp.mcp_api import McpApiContainer
from topicgate.mcp.middleware import ErrorHandlingMiddleware, LoggingMiddleware
from topicgate.mcp.publish_api import PublishAPI
from topicgate.mcp.subscription_api import SubscriptionAPI
from topicgate.mcp.topic_api import TopicAPI

class Server:
    def __init__(self):
        self.mcp = FastMCP(
            name="topicgate",
            instructions="Inspect and manage MQTT brokers, topics, and subscriptions.",
            lifespan=self._lifespan,
            middleware=[ErrorHandlingMiddleware(), LoggingMiddleware()],
            mask_error_details=True,
        )

        self.dependencies = AppDependencies()
        self.services = ServiceContainer(self.dependencies)

        runtime = self.dependencies.runtime

        self.mcp_container = McpApiContainer(
            [
                BrokerAPI(runtime),
                ConnectionAPI(runtime),
                PublishAPI(runtime),
                SubscriptionAPI(runtime),
                TopicAPI(runtime),
            ]
        )
        self.mcp_container.register(self.mcp)

    def run(self) -> None:
        self.mcp.run()

    @asynccontextmanager
    async def _lifespan(self, _server: FastMCP) -> AsyncIterator[None]:
        try:
            await self.services.start_services()
            yield
        finally:
            await self.services.stop_services()


def run() -> int:
    server = Server()

    try:
        server.run()
    except Exception as error:
        print(error, file=sys.stderr)
        return 1

    return 0
