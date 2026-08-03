from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.core.config.app_config import AppConfig
import asyncio

from smart_home_observer.infrastructure.repository.chicken_door_repository import ChickenDoorRepository

class App:
    def __init__(self, config: AppConfig):
        self.config = config
        self.name = "SmartHomeObserver"

        self.chicken_door_repo = ChickenDoorRepository(self.config.mqtt)

    async def start(self):
        await self.chicken_door_repo.start()

    async def stop(self):
        await self.chicken_door_repo.stop()

    async def wait_forever(self):
        await asyncio.Event().wait()

async def main():
    config = ConfigLoader().load_config()
    app = App(config)

    try:
        await app.start()
        await app.wait_forever()
    finally:
        await app.stop()

def run():
    asyncio.run(main())

if __name__ == "__main__":
    run()
