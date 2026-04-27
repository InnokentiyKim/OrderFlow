import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class OrderCreatedEvent(BaseModel):
    """Kafka event published after a new order is saved to DB."""

    event_type: str = "order.created"
    event_id: uuid.UUID
    saga_id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    items: list[Any]
    total_amount: Decimal
    timestamp: datetime
