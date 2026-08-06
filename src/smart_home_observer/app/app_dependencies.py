from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.infrastructure.repository.broker_repository import BrokerRepository
from smart_home_observer.infrastructure.repository.observer_repository import ObserverRepository


class AppDependencies:
    """Builds application components and exposes their lifecycle order."""

    def __init__(self) -> None:
        # Load configuration
        self.broker_repository = BrokerRepository()

        profile = self.broker_repository.get_profile()

        self.observer_model_repository = ObserverRepository(
            profile.config,
            list(profile.workspace.subscriptions),
            self.broker_repository.get_observer_model(),
        )
        self.service_items: tuple[ServiceItem, ...] = (self.observer_model_repository,)
