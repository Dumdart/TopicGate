from topicgate.app.services.service_item import ServiceItem
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)


class PersistenceLifecycle(ServiceItem):
    """Close application-owned persistence resources after runtime shutdown."""

    def __init__(
        self,
        topic_messages: TopicMessageRepository,
        database: DatabaseContext,
    ) -> None:
        self._topic_messages = topic_messages
        self._database = database

    async def start(self) -> None:
        """Persistence resources are ready immediately after construction."""

    async def stop(self) -> None:
        """Drain queued messages before disposing database connections."""
        self._topic_messages.close()
        self._database.dispose()
