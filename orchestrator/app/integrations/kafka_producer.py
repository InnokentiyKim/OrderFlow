import json
import uuid
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from app.common.enums import EventTypeEnum
from app.core.config import app_config
from app.models.events import (
    ReserveInventoryCommand,
    ChargePaymentCommand,
    SagaCompletedEvent,
    SagaCancelledEvent,
    SagaFailedEvent,
    DLQEvent,
)

logger = structlog.get_logger(__name__)

_COMMAND_MODELS = {
    EventTypeEnum.RESERVE_INVENTORY: ReserveInventoryCommand,
    EventTypeEnum.CHARGE_PAYMENT: ChargePaymentCommand,
}

_EVENT_MODELS = {
    EventTypeEnum.SAGA_COMPLETED: SagaCompletedEvent,
    EventTypeEnum.SAGA_CANCELLED: SagaCancelledEvent,
    EventTypeEnum.SAGA_FAILED: SagaFailedEvent,
}


class KafkaProducerClient:
    def __init__(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=app_config.broker.kafka_bootstrap_servers,
            acks=app_config.broker.kafka_acks,
            enable_idempotence=app_config.broker.kafka_enable_idempotence,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
        )

    async def start(self) -> None:
        await self._producer.start()
        await logger.ainfo("Kafka producer started")

    async def stop(self) -> None:
        await self._producer.stop()
        await logger.ainfo("Kafka producer stopped")

    async def send_command(
        self,
        topic: str,
        command_type: EventTypeEnum,
        saga_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        model_cls = _COMMAND_MODELS.get(command_type)
        if model_cls is None:
            raise ValueError(f"Unknown command_type: {command_type!r}")

        command = model_cls(saga_id=saga_id, order_id=order_id, payload=payload)
        message = command.to_kafka_message()

        await self._producer.send_and_wait(topic, value=message, key=str(saga_id))
        await logger.ainfo(
            "Sent command",
            topic=topic,
            command_type=command_type,
            saga_id=str(saga_id),
            order_id=str(order_id),
        )

    async def send_event(
        self,
        topic: str,
        event_type: EventTypeEnum,
        saga_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        model_cls = _EVENT_MODELS.get(event_type)
        if model_cls is None:
            raise ValueError(f"Unknown event_type: {event_type!r}")

        extra: dict[str, Any] = {}
        if event_type is EventTypeEnum.SAGA_FAILED:
            extra["retry_count"] = payload.get("retry_count", 0)

        event = model_cls(saga_id=saga_id, order_id=order_id, payload=payload, **extra)
        message = event.to_kafka_message()

        await self._producer.send_and_wait(topic, value=message, key=str(saga_id))
        await logger.ainfo(
            "Sent event",
            topic=topic,
            event_type=event_type,
            saga_id=str(saga_id),
            order_id=str(order_id),
        )

    async def send_to_dlq(
        self,
        topic: str,
        saga_id: uuid.UUID,
        order_id: uuid.UUID,
        original_state: str,
        retry_count: int,
        last_error: str | None,
        original_event: dict[str, Any] | None = None,
    ) -> None:
        dlq = DLQEvent(
            saga_id=saga_id,
            order_id=order_id,
            original_state=original_state,
            retry_count=retry_count,
            last_error=last_error,
            original_event=original_event or {},
        )
        message = dlq.to_kafka_message()

        await self._producer.send_and_wait(topic, value=message, key=str(saga_id))
        await logger.aerror(
            "Sent to DLQ",
            topic=topic,
            saga_id=str(saga_id),
            order_id=str(order_id),
            retry_count=retry_count,
            last_error=last_error,
        )
