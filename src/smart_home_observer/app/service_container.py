from smart_home_observer.app.app_dependencies import AppDependencies
from smart_home_observer.app.service_item import ServiceItem


class ServiceContainer:
    """Starts registered services in order and stops them in reverse order."""

    def __init__(self, dependencies: AppDependencies) -> None:
        self._service_items: tuple[ServiceItem, ...] = dependencies.service_items
        self._started_items: list[ServiceItem] = []

    async def start_services(self) -> None:
        for service_item in self._service_items:
            await service_item.start()
            self._started_items.append(service_item)

    async def stop_services(self) -> None:
        while self._started_items:
            service_item = self._started_items.pop()
            await service_item.stop()
