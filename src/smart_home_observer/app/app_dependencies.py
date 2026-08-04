from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.infrastructure.repository.observer_repository import ObserverRepository
from smart_home_observer.services.topic_service import TopicService


class AppDependencies:
    """Builds application components and exposes their lifecycle order."""

    def __init__(self, config: AppConfig) -> None:
        self.observer_model_repository = ObserverRepository(
            config.mqtt, TopicService.get_topic_filters()
        )
        self.service_items: tuple[ServiceItem, ...] = (self.observer_model_repository,)
