from pathlib import Path
from unittest.mock import MagicMock, patch

from topicgate.app.app_dependencies import AppDependencies
from topicgate.core.config.mqtt_config import MqttConfig


def test_app_dependencies_uses_os_credentials_for_broker_profiles(
    tmp_path: Path,
) -> None:
    database = MagicMock()
    profile = MagicMock()
    profile.config = MqttConfig("broker", 1883, "observer", "entered-secret")
    profile.workspace.subscriptions = ()
    profile.workspace.model = MagicMock()
    broker_profiles = MagicMock()
    broker_profiles.get_profile.return_value = profile
    broker_profiles.get_all_profiles.return_value = (profile,)
    credential_store = MagicMock()

    with (
        patch(
            "topicgate.app.app_dependencies.DatabaseContext",
            return_value=database,
        ),
        patch(
            "topicgate.app.app_dependencies.BrokerProfileService",
            return_value=broker_profiles,
        ) as repository_type,
        patch(
            "topicgate.app.app_dependencies.TopicMessageRepository"
        ) as message_type,
        patch("topicgate.app.app_dependencies.ObserverMqttRepository"),
    ):
        dependencies = AppDependencies(
            data_dir=tmp_path,
            credential_store=credential_store,
        )

    repository_type.assert_called_once_with(
        database,
        credential_store=credential_store,
        runtime_state=dependencies.broker_runtime_state,
        topic_messages=dependencies.topic_messages,
    )
    message_type.assert_called_once_with(database)
    assert dependencies.service_items == (
        dependencies.persistence,
        dependencies.runtime,
    )
