from smart_home_observer.app.app_dependencies import AppDependencies
from smart_home_observer.app.service_container import ServiceContainer
from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.core.config.app_config import AppConfig
import asyncio


class App:
    def __init__(self, config: AppConfig):
        self.config = config
        self.name = "SmartHomeObserver"

        self.dependencies = AppDependencies(config)
        self.service_container = ServiceContainer(self.dependencies)

    async def start(self) -> None:
        await self.service_container.start_services()

    async def stop(self) -> None:
        await self.service_container.stop_services()

    async def wait_forever(self) -> None:
        await asyncio.Event().wait()


async def main() -> None:
    config = ConfigLoader().load_config()
    app = App(config)

    try:
        await app.start()
        await app.wait_forever()
    finally:
        await app.stop()

def run() -> None:
    asyncio.run(main())

if __name__ == "__main__":
    run()
