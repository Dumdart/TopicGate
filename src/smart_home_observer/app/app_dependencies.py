from collections.abc import Callable
from dataclasses import replace
from getpass import getpass

from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.infrastructure.database.database_context import DatabaseContext
from smart_home_observer.infrastructure.repository.broker_repository import BrokerRepository
from smart_home_observer.infrastructure.repository.observer_mqtt_repository import (
    ObserverMqttRepository,
)


class AppDependencies:
    """Build application components and expose their lifecycle order."""

    def __init__(self, password_reader: Callable[[str], str] = getpass) -> None:
        self._db_context = DatabaseContext("sqlite:///smart_observer.db")
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
