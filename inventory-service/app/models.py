import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CommandType(StrEnum):
    RESERVE_INVENTORY = "reserve_inventory"
    CANCEL_RESERVATION = "cancel_reservation"


class Command(BaseModel):
    command_type: CommandType
    saga_id: str
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any] = Field(default_factory=dict)


class InventoryEvent(BaseModel):
    event_type: str
    saga_id: str
    order_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_kafka_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    def kafka_key(self) -> bytes:
        return self.saga_id.encode()

