import asyncio

from topicgate.app.service_container import ServiceContainer


class FakeService:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    async def start(self) -> None:
        self.events.append(f"start:{self.name}")

    async def stop(self) -> None:
        self.events.append(f"stop:{self.name}")


class FakeDependencies:
    def __init__(self, service_items: tuple[FakeService, ...]) -> None:
        self.service_items = service_items


def test_container_starts_services_in_registration_order_and_stops_in_reverse() -> None:
    async def scenario() -> None:
        events: list[str] = []
        first = FakeService("first", events)
        second = FakeService("second", events)
        container = ServiceContainer(FakeDependencies((first, second)))

        await container.start_services()
        await container.stop_services()

        assert events == [
            "start:first",
            "start:second",
            "stop:second",
            "stop:first",
        ]

    asyncio.run(scenario())


def test_container_only_stops_services_that_started() -> None:
    async def scenario() -> None:
        events: list[str] = []
        service = FakeService("service", events)
        container = ServiceContainer(FakeDependencies((service,)))

        await container.stop_services()

        assert events == []

    asyncio.run(scenario())
