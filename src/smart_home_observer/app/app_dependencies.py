from ast import Sub

from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.core.config.config_loader import AppConfig
from smart_home_observer.infrastructure.database.database_context import DatabaseContext
from smart_home_observer.infrastructure.repository.broker_repository import BrokerRepository
from smart_home_observer.infrastructure.repository.config_repository import ConfigRepository
from smart_home_observer.infrastructure.repository.observer_mqtt_repository import ObserverMqttRepository
from smart_home_observer.infrastructure.repository.subscription_repository import SubscriptionRepository



class AppDependencies:
    """Builds application components and exposes their lifecycle order."""

    def __init__(self) -> None:
        # Load configuration
        self._db_context = DatabaseContext("sqlite:///smart_observer.db")

        self.config_repository = ConfigRepository(self._db_context)
        self.broker_repository = BrokerRepository(self._db_context)
        self.subscription_repository = SubscriptionRepository(self._db_context)

        profile = self.broker_repository.get_profile()


        self.observer_model_repository = ObserverMqttRepository(
            profile.config,
            list(profile.workspace.subscriptions),
            self.broker_repository.get_observer_model(),
        )

        self.service_items: tuple[ServiceItem, ...] = (self.observer_model_repository,)

        self.__test_()

    def __test_(self) -> None:
        from dataclasses import replace
        from getpass import getpass


        password = getpass("Enter MQTT password: ")
        if not password:
            print("No password entered; keeping the current MQTT configuration.")
            return

        #updated_config = replace(
        #    self.profile.app_config,
        #    mqtt=replace(self.profile.app_config.mqtt, password=password),
        #)

        #self.config_repository.update_app_config(updated_config)
        #self.config_repository.is_password_set = True
