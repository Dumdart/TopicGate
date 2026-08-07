from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.infrastructure.repository.broker_repository import BrokerRepository
from smart_home_observer.infrastructure.repository.observer_mqtt_repository import ObserverMqttRepository



class AppDependencies:
    """Builds application components and exposes their lifecycle order."""

    def __init__(self) -> None:
        #self._db_context = DatabaseContext("sqlite:///smart_observer.db")

        # Load configuration
        self.broker_repository = BrokerRepository()
        profile = self.broker_repository.get_profile()

        self.observer_model_repository = ObserverMqttRepository(
            profile.config,
            list(profile.workspace.subscriptions),
            self.broker_repository.get_observer_model(),
        )

        self.service_items: tuple[ServiceItem, ...] = (self.observer_model_repository,)
