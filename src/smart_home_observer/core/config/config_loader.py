from collections.abc import Mapping

from dotenv import load_dotenv
import os

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig


class ConfigLoader:
    def load_config(self, dotenv_path: str | None = None) -> AppConfig:
        load_dotenv(dotenv_path=dotenv_path)
        return self.config_from_mapping(os.environ)

    def config_from_mapping(self, values: Mapping[str, str]) -> AppConfig:
        return AppConfig(
            mqtt=MqttConfig(
                host=values['MQTT_HOST'],
                port=int(values['MQTT_PORT']),
                username=values['MQTT_USERNAME'],
                password=values['MQTT_PASSWORD'],
                use_tls=values['MQTT_USE_TLS'].strip().lower() == 'true',
            )
        )
