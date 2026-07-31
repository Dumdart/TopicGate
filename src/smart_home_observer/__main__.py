from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.infrastructure.mqtt.basic_callbacks import BasicCallbacks
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate

import asyncio

class App:
    def __init__(self, config: AppConfig):
        self.config = config
        self.name = "SmartHomeObserver"
        self.mqtt_gate = MqttGate(config.mqtt, BasicCallbacks(), None)

    async def start(self):
        await self.mqtt_gate.start()
        await self.mqtt_gate.publish("Hllo")
        await self.mqtt_gate.subscribe()

    async def stop(self):
        await self.mqtt_gate.stop()

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
