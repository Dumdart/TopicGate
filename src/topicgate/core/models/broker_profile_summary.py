from dataclasses import dataclass
from uuid import UUID


@dataclass
class BrokerProfileSummary:
    id: UUID
    name: str
    host: str
    port: int
    username: str
    use_tls: bool
