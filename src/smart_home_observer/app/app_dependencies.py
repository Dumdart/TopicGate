from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.infrastructure.repository.chicken_door_repository import ChickenDoorRepository


class AppDependencies:
    """Builds application components and exposes their lifecycle order."""

    def __init__(self, config: AppConfig) -> None:
        self.chicken_door_repo = ChickenDoorRepository(config.mqtt)
        self.service_items: tuple[ServiceItem, ...] = (self.chicken_door_repo,)
