from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.infrastructure.database.mappers.mapper_helper import (
    MapperHelper,
)
from smart_home_observer.infrastructure.database.models.app_config_row import (
    AppConfigRow,
)
from smart_home_observer.infrastructure.database.models.mqtt_config_row import (
    MqttConfigRow,
)


class ConfigMapper:
    """Converts between configuration models and database rows."""

    @staticmethod
    def to_app_config_row(app_config: AppConfig) -> AppConfigRow:
        return AppConfigRow(
            mqtt_config_row=ConfigMapper.to_mqtt_config_row(app_config.mqtt),
        )

    @staticmethod
    def to_mqtt_config_row(mqtt_config: MqttConfig) -> MqttConfigRow:
        return MqttConfigRow(
            host=mqtt_config.host,
            port=mqtt_config.port,
            username=mqtt_config.username,
            use_tls=mqtt_config.use_tls,
        )

    @staticmethod
    def to_app_config(app_config_row: AppConfigRow) -> AppConfig:
        return AppConfig(
            id=MapperHelper.optional_int(app_config_row.id, "id"),
            mqtt=ConfigMapper.to_mqtt_config(app_config_row.mqtt_config_row),
        )

    @staticmethod
    def to_mqtt_config(mqtt_config_row: MqttConfigRow) -> MqttConfig:
        return MqttConfig(
            id=MapperHelper.optional_int(mqtt_config_row.id, "id"),
            host=MapperHelper.required_str(mqtt_config_row.host, "host"),
            port=MapperHelper.required_int(mqtt_config_row.port, "port"),
            username=MapperHelper.required_str(mqtt_config_row.username, "username"),
            use_tls=MapperHelper.required_bool(mqtt_config_row.use_tls, "use_tls"),
            password=""
        )
