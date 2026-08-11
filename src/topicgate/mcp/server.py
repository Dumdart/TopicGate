from contextlib import asynccontextmanager

from fastmcp import FastMCP

from topicgate.app.app_dependencies import AppDependencies
from topicgate.app.service_container import ServiceContainer
from topicgate.mcp.broker_api import BrokerAPI
from topicgate.mcp.connection_api import ConnectionAPI
from topicgate.mcp.mcp_api import McpApiContainer
from topicgate.mcp.publish_api import PublishAPI
from topicgate.mcp.subscription_api import SubscriptionAPI
from topicgate.mcp.topic_api import TopicAPI


class Server:
    def __init__(self):
        self.mcp = FastMCP(
            name="topicgate",
            instructions="Inspect and manage MQTT brokers, topics, and subscriptions.",
            lifespan=self._lifespan
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
    async def _lifespan(self, _server:FastMCP):
        try:
            await self.services.start_services()
            yield {"started_at": "2024-01-01"}
        finally:
            await self.services.stop_services()

def run() -> int:
    server = Server()

    try:
        server.run()
    except Exception as e:
        print(e)
        return 1

    return 0
