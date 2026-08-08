from collections.abc import Callable
from dataclasses import replace
from getpass import getpass
from pathlib import Path

from topicgate.app.service_item import ServiceItem
from topicgate.core.config.config_loader import ConfigLoader
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.broker_repository import BrokerRepository
from topicgate.infrastructure.repository.observer_mqtt_repository import (
    ObserverMqttRepository,
)
from topicgate.paths import prepare_database_path, sqlite_url


class AppDependencies:
    """Build application components and expose their lifecycle order."""

    def __init__(
        self,
        password_reader: Callable[[str], str] = getpass,
        data_dir: Path | None = None,
        legacy_database: Path | None = None,
    ) -> None:
        database_path = prepare_database_path(data_dir, legacy_database)
        self._db_context = DatabaseContext(sqlite_url(database_path))
        runtime_settings = ConfigLoader().load_config()
        entered_password = password_reader("Enter MQTT password: ")
        if entered_password:
            runtime_settings = replace(
                runtime_settings,
                mqtt=replace(runtime_settings.mqtt, password=entered_password),
            )
        self.broker_repository = BrokerRepository(
            self._db_context,
            runtime_settings,
        )
        profile = self.broker_repository.get_profile()
        self.observer_model_repository = ObserverMqttRepository(
            profile.config,
            list(profile.workspace.subscriptions),
            profile.workspace.model,
        )
        self.service_items: tuple[ServiceItem, ...] = (
            self.observer_model_repository,
        )
