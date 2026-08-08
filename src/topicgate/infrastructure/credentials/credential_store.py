from typing import Protocol
from uuid import UUID


class CredentialStore(Protocol):
    def get_password(self, profile_id: UUID) -> str | None: ...

    def set_password(self, profile_id: UUID, password: str, /) -> None: ...

    def delete_password(self, profile_id: UUID) -> None: ...
