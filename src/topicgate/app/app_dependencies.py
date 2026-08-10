from pathlib import Path

from topicgate.app.service_item import ServiceItem
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.credentials.credential_store import CredentialStore
from topicgate.infrastructure.credentials.os_credential_store import OSCredentialStore
from topicgate.infrastructure.repository.broker_repository import BrokerRepository
from topicgate.infrastructure.repository.observer_mqtt_repository import (
    ObserverMqttRepository,
)
from topicgate.paths import prepare_database_path, sqlite_url


class AppDependencies:
    """Build application components and expose their lifecycle order."""

    def __init__(
        self,
        data_dir: Path | None = None,
        legacy_database: Path | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        database_path = prepare_database_path(data_dir, legacy_database)
        self._db_context = DatabaseContext(sqlite_url(database_path))
        self.credential_store = (
            OSCredentialStore() if credential_store is None else credential_store
        )
        self.broker_repository = BrokerRepository(
            self._db_context,
            credential_store=self.credential_store,
        )
        profile = self.broker_repository.get_profile()
        self.observer_model_repositories = {
            item.id: ObserverMqttRepository(
                item.config,
                list(item.workspace.subscriptions),
                item.workspace.model,
            )
            for item in self.broker_repository.get_all_profiles()
        }
        self.observer_model_repository = self.observer_model_repositories[profile.id]
        self.runtime = TopicGateRuntime(
            self.broker_repository,
            self.observer_model_repositories,
            profile.id,
        )
        self.service_items: tuple[ServiceItem, ...] = (
            self.runtime,
        )
