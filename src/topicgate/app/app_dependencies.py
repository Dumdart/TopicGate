from pathlib import Path
from uuid import UUID

from topicgate.app.services.service_item import ServiceItem
from topicgate.app.services.persistence_lifecycle import PersistenceLifecycle
from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.app.broker_runtime_state import BrokerRuntimeState
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.interfaces.observer_repository import ObserverRepository
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.credentials.credential_store import CredentialStore
from topicgate.infrastructure.credentials.os_credential_store import OSCredentialStore
from topicgate.infrastructure.repository.observer_mqtt_repository import (
    ObserverMqttRepository,
)
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)
from topicgate.infrastructure.repository.observation_retention_policy_repository import (
    ObservationRetentionPolicyRepository,
)
from topicgate.paths import prepare_database_path, sqlite_url


class AppDependencies:
    """Build application components and expose their lifecycle order."""

    def __init__(
        self,
        data_dir: Path | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:

        database_path = prepare_database_path(data_dir)
        self._db_context = DatabaseContext(sqlite_url(database_path))
        self.credential_store = (
            OSCredentialStore() if credential_store is None else credential_store
        )

        self.broker_runtime_state = BrokerRuntimeState()
        self.topic_messages = TopicMessageRepository(self._db_context)
        self.observation_retention_policy = ObservationRetentionPolicyRepository(
            self._db_context
        )
        self.persistence = PersistenceLifecycle(
            self.topic_messages,
            self._db_context,
        )
        self.broker_profiles = BrokerProfileService(
            self._db_context,
            credential_store=self.credential_store,
            runtime_state=self.broker_runtime_state,
            topic_messages=self.topic_messages,
        )
        profile = self.broker_profiles.get_profile()

        self.broker_runtime_state.repositories.update(
            {
                item.id: self._create_observer_repository(item)
                for item in self.broker_profiles.get_all_profiles()
            }
        )

        self.runtime = TopicGateRuntime(
            self.broker_profiles,
             self.broker_runtime_state.repositories,
            profile.id,
            self._create_observer_repository,
        )

        self.service_items: tuple[ServiceItem, ...] = (
            self.persistence,
            self.runtime,
        )

    @staticmethod
    def _create_observer_repository(profile: BrokerProfile) -> ObserverRepository:
        return ObserverMqttRepository(
            profile.config,
            list(profile.workspace.subscriptions),
            profile.workspace.model,
        )
