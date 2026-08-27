from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class OrderType(str, Enum):
    RECEIVED_ASC = "received_asc"
    RECEIVED_DESC = "received_desc"
    TOPIC_ASC = "topic_asc"
    TOPIC_DESC = "topic_desc"
    MESSAGE_COUNT_ASC = "message_count_asc"
    MESSAGE_COUNT_DESC = "message_count_desc"
    PAYLOAD_SIZE_ASC = "payload_size_asc"
    PAYLOAD_SIZE_DESC = "payload_size_desc"


@dataclass(frozen=True)
class MessageFilter:
    broker_id: UUID
    topic_filter: str = "#"
    after: datetime | None = None
    before: datetime | None = None
    order: OrderType = OrderType.RECEIVED_DESC
    limit: int = 50
