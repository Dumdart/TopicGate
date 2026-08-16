from unittest.mock import MagicMock

from topicgate.app.services.persistence_lifecycle import PersistenceLifecycle


async def test_persistence_lifecycle_closes_repository_before_database() -> None:
    events: list[str] = []
    messages = MagicMock()
    database = MagicMock()
    messages.close.side_effect = lambda: events.append("messages")
    database.dispose.side_effect = lambda: events.append("database")
    lifecycle = PersistenceLifecycle(messages, database)

    await lifecycle.start()
    await lifecycle.stop()

    assert events == ["messages", "database"]
