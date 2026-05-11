import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.enums import EventTypeEnum


class BaseKafkaMessage(BaseModel):
    """Base model for Kafka messages with common configuration."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        frozen=False,
    )

    saga_id: uuid.UUID
    order_id: uuid.UUID

    @field_validator("saga_id", "order_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        return uuid.UUID(str(v))


class OrderCreatedEvent(BaseKafkaMessage):
    """Event representing a newly created order."""

    event_type: Literal[EventTypeEnum.ORDER_CREATED] = EventTypeEnum.ORDER_CREATED  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_amount: Decimal = Decimal("0")
    currency: str = "USD"

    @field_validator("event_id", mode="before")
    @classmethod
    def coerce_event_id(cls, v: Any) -> uuid.UUID:
        if v is None:
            return uuid.uuid4()
        if isinstance(v, uuid.UUID):
            return v
        return uuid.UUID(str(v))

    @model_validator(mode="before")
    @classmethod
    def alias_message_id(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Takes care of backward compatibility: if event_id is missing but message_id is present, use it."""
        if "event_id" not in data and "message_id" in data:
            data["event_id"] = data["message_id"]
        return data

    @property
    def order_saga_payload(self) -> dict[str, Any]:
        """Prepares the payload for saga state from the order created event."""
        return {
            "order_id": str(self.order_id),
            "user_id": self.user_id,
            "items": self.items,
            "total_amount": str(self.total_amount),
            "currency": self.currency,
        }

    @property
    def order_command_payload(self) -> dict[str, Any]:
        """Prepares the payload for commands based on the order created event."""
        return {"items": self.items}


class InventoryReservedEvent(BaseKafkaMessage):
    """Inventory successfully reserved."""

    event_type: Literal[EventTypeEnum.INVENTORY_RESERVED] = (
        EventTypeEnum.INVENTORY_RESERVED
    )  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class InventoryReserveFailedEvent(BaseKafkaMessage):
    """Inventory reservation failed."""

    event_type: Literal[EventTypeEnum.INVENTORY_RESERVE_FAILED] = (
        EventTypeEnum.INVENTORY_RESERVE_FAILED
    )  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    error: str = EventTypeEnum.INVENTORY_RESERVE_FAILED


class PaymentSucceededEvent(BaseKafkaMessage):
    """Payment successfully charged."""

    event_type: Literal[EventTypeEnum.PAYMENT_SUCCEEDED] = (
        EventTypeEnum.PAYMENT_SUCCEEDED
    )  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class PaymentFailedEvent(BaseKafkaMessage):
    """Payment charge failed."""

    event_type: Literal[EventTypeEnum.PAYMENT_FAILED] = EventTypeEnum.PAYMENT_FAILED  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    error: str = EventTypeEnum.PAYMENT_FAILED


class InventoryReservationCancelledEvent(BaseKafkaMessage):
    """Inventory reservation cancelled successfully."""

    event_type: Literal[EventTypeEnum.INVENTORY_RESERVATION_CANCELLED] = (
        EventTypeEnum.INVENTORY_RESERVATION_CANCELLED
    )  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class InventoryReservationCancelFailedEvent(BaseKafkaMessage):
    """Inventory reservation cancellation failed."""

    event_type: Literal[EventTypeEnum.INVENTORY_RESERVATION_CANCEL_FAILED] = (
        EventTypeEnum.INVENTORY_RESERVATION_CANCEL_FAILED
    )  # type: ignore
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    error: str = EventTypeEnum.INVENTORY_RESERVATION_CANCEL_FAILED


# Discriminated union for incoming events from Kafka
IncomingEvent = Annotated[
    OrderCreatedEvent
    | InventoryReservedEvent
    | InventoryReserveFailedEvent
    | PaymentSucceededEvent
    | PaymentFailedEvent
    | InventoryReservationCancelledEvent
    | InventoryReservationCancelFailedEvent,
    Field(discriminator="event_type"),
]


def parse_incoming_event(data: dict[str, Any]) -> IncomingEvent:
    """Parse incoming Kafka message into the appropriate event model based on the event_type discriminator."""
    from pydantic import TypeAdapter

    adapter: TypeAdapter[IncomingEvent] = TypeAdapter(IncomingEvent)
    return adapter.validate_python(data)


class ReserveInventoryCommand(BaseModel):
    """Command to reserve inventory."""

    model_config = ConfigDict(populate_by_name=True)

    command_type: EventTypeEnum = EventTypeEnum.RESERVE_INVENTORY
    saga_id: uuid.UUID
    order_id: uuid.UUID
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_kafka_message(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ChargePaymentCommand(BaseModel):
    """Command to charge payment."""

    model_config = ConfigDict(populate_by_name=True)

    command_type: EventTypeEnum = EventTypeEnum.CHARGE_PAYMENT
    saga_id: uuid.UUID
    order_id: uuid.UUID
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_kafka_message(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SagaCompletedEvent(BaseModel):
    """Saga completed successfully."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: EventTypeEnum = EventTypeEnum.SAGA_COMPLETED
    saga_id: uuid.UUID
    order_id: uuid.UUID
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=lambda: {"status": "COMPLETED"})

    def to_kafka_message(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SagaCancelledEvent(BaseModel):
    """Saga cancelled (compensation completed)."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: EventTypeEnum = EventTypeEnum.SAGA_CANCELLED
    saga_id: uuid.UUID
    order_id: uuid.UUID
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=lambda: {"status": "CANCELLED"})

    def to_kafka_message(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SagaFailedEvent(BaseModel):
    """Saga failed (retry attempts exhausted)."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: EventTypeEnum = EventTypeEnum.SAGA_FAILED
    saga_id: uuid.UUID
    order_id: uuid.UUID
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    retry_count: int = 0
    payload: dict[str, Any] = Field(default_factory=lambda: {"status": "FAILED"})

    @model_validator(mode="after")
    def sync_retry_count_to_payload(self) -> "SagaFailedEvent":
        self.payload["retry_count"] = self.retry_count
        return self

    def to_kafka_message(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DLQEvent(BaseModel):
    """Event representing a message sent to the Dead Letter Queue after exhausting retries."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: EventTypeEnum = EventTypeEnum.DLQ_EVENT
    saga_id: uuid.UUID
    order_id: uuid.UUID
    original_state: str
    retry_count: int
    last_error: str | None = None
    failed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    original_event: dict[str, Any] = Field(default_factory=dict)

    @field_validator("saga_id", "order_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        return uuid.UUID(str(v))

    def to_kafka_message(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_kafka_message(cls, data: dict[str, Any]) -> "DLQEvent":
        return cls.model_validate(data)
