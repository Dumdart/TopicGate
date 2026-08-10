from unittest.mock import patch
from uuid import uuid4

from topicgate.infrastructure.credentials.os_credential_store import (
    OSCredentialStore,
)


def test_get_password_reads_profile_password_from_keyring() -> None:
    store = OSCredentialStore()
    profile_id = uuid4()

    with patch(
        "topicgate.infrastructure.credentials.os_credential_store.keyring.get_password",
        return_value="secret",
    ) as get_password:
        password = store.get_password(profile_id)

    assert password == "secret"
    get_password.assert_called_once_with(
        "TopicGate MQTT", f"profile_{profile_id}"
    )


def test_set_password_writes_profile_password_to_keyring() -> None:
    store = OSCredentialStore()
    profile_id = uuid4()

    with patch(
        "topicgate.infrastructure.credentials.os_credential_store.keyring.set_password"
    ) as set_password:
        store.set_password(profile_id, "secret")

    set_password.assert_called_once_with(
        "TopicGate MQTT", f"profile_{profile_id}", "secret"
    )


def test_delete_password_removes_profile_password_from_keyring() -> None:
    store = OSCredentialStore()
    profile_id = uuid4()

    with patch(
        "topicgate.infrastructure.credentials.os_credential_store.keyring.delete_password"
    ) as delete_password:
        store.delete_password(profile_id)

    delete_password.assert_called_once_with(
        "TopicGate MQTT", f"profile_{profile_id}"
    )
