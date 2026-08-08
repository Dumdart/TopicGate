from uuid import UUID

import pytest


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.passwords: dict[UUID, str] = {}

    def get_password(self, profile_id: UUID) -> str | None:
        return self.passwords.get(profile_id)

    def set_password(self, profile_id: UUID, password: str, /) -> None:
        self.passwords[profile_id] = password

    def delete_password(self, profile_id: UUID) -> None:
        self.passwords.pop(profile_id, None)


@pytest.fixture
def credential_store() -> MemoryCredentialStore:
    return MemoryCredentialStore()
