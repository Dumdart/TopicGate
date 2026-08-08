from pathlib import Path
from unittest.mock import MagicMock, patch

from topicgate.app.app_dependencies import AppDependencies
from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.mqtt_config import MqttConfig


def test_app_dependencies_applies_entered_password_only_to_runtime_settings(
    tmp_path: Path,
) -> None:
    stored_settings = AppConfig(
        MqttConfig("broker", 1883, "observer", "environment-secret")
    )
    database = MagicMock()
    profile = MagicMock()
    profile.config = MqttConfig("broker", 1883, "observer", "entered-secret")
    profile.workspace.subscriptions = ()
    profile.workspace.model = MagicMock()
    broker_repository = MagicMock()
    broker_repository.get_profile.return_value = profile

    with (
        patch(
            "topicgate.app.app_dependencies.DatabaseContext",
            return_value=database,
        ),
        patch(
            "topicgate.app.app_dependencies.ConfigLoader"
        ) as config_loader,
        patch(
            "topicgate.app.app_dependencies.BrokerRepository",
            return_value=broker_repository,
        ) as repository_type,
        patch("topicgate.app.app_dependencies.ObserverMqttRepository"),
    ):
        config_loader.return_value.load_config.return_value = stored_settings

        AppDependencies(
            password_reader=lambda _prompt: "entered-secret",
            data_dir=tmp_path,
            legacy_database=tmp_path / "missing.db",
        )

    runtime_settings = repository_type.call_args.args[1]
    assert runtime_settings.mqtt.host == stored_settings.mqtt.host
    assert runtime_settings.mqtt.username == stored_settings.mqtt.username
    assert runtime_settings.mqtt.password == "entered-secret"
    assert stored_settings.mqtt.password == "environment-secret"
