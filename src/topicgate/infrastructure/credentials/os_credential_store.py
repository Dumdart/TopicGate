from uuid import UUID

import keyring


class OSCredentialStore:
    _SERVICE = "TopicGate MQTT"

    @staticmethod
    def _account(profile_id: UUID) -> str:
        return f"profile_{profile_id}"

    def get_password(self, profile_id: UUID) -> str | None:
        return keyring.get_password(self._SERVICE, self._account(profile_id))

    def set_password(self, profile_id: UUID, password: str, /) -> None:
        keyring.set_password(self._SERVICE, self._account(profile_id), password)

    def delete_password(self, profile_id: UUID) -> None:
        keyring.delete_password(self._SERVICE, self._account(profile_id))
