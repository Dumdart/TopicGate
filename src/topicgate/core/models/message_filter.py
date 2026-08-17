from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MessageFilter:
    after: datetime | None = None
    before: datetime | None = None
    topics: tuple[str, ...] = field(default_factory=tuple)
