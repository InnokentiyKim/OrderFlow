from abc import ABC, abstractmethod

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import EventTypeEnum, SagaStateEnum
from app.core.config import BrokerSettings, RetrySettings
from app.integrations.dao.saga import SagaStateDAO
from app.integrations.kafka_producer import KafkaProducerClient
from app.models.events import IncomingEvent, OrderCreatedEvent
from app.models.saga_state import SagaState
from app.saga.publisher import EventPublisher

logger = structlog.get_logger(__name__)


class HandlerFunc(ABC):
    """Base class for all event handlers. Defines the common interface and dependencies."""

    @abstractmethod
    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None: ...


class HandleOrderCreated(HandlerFunc):
    """Create new saga on order.created and send reserve command."""

    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None:
        assert isinstance(event, OrderCreatedEvent)

        new_saga = SagaState(
            saga_id=event.saga_id,
            order_id=event.order_id,
            state=SagaStateEnum.CREATED,
            payload=event.order_saga_payload,
        )
        await dao.create(session, new_saga)
        await dao.update_state(session, new_saga, SagaStateEnum.INVENTORY_RESERVING)
        await session.commit()

        await logger.ainfo(
            "Saga created, transitioning to INVENTORY_RESERVING",
            saga_id=str(event.saga_id),
            order_id=str(event.order_id),
        )
        await producer.send_command(
            topic=broker_cfg.kafka_topic_inventory_commands,
            command_type=EventTypeEnum.RESERVE_INVENTORY,
            saga_id=event.saga_id,
            order_id=event.order_id,
            payload=event.order_command_payload,
        )


class HandleOrderCreatedDuplicate(HandlerFunc):
    """Received duplicate order.created — saga already exists, re-sending reserve command."""

    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None:
        await logger.ainfo(
            "Duplicate order.created received, re-sending inventory command",
            saga_id=str(saga.saga_id) if saga else "unknown",
            current_state=saga.state if saga else None,
        )
        if saga is not None and saga.state == SagaStateEnum.INVENTORY_RESERVING:
            await producer.send_command(
                topic=broker_cfg.kafka_topic_inventory_commands,
                command_type=EventTypeEnum.RESERVE_INVENTORY,
                saga_id=saga.saga_id,
                order_id=saga.order_id,
                payload=saga.order_command_payload,
            )


class HandleInventoryReserved(HandlerFunc):
    """Inventory reserved — transition to payment."""

    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None:
        assert saga is not None

        await dao.reset_retry_count(session, saga)
        await dao.update_state(session, saga, SagaStateEnum.INVENTORY_RESERVED)
        await dao.update_state(session, saga, SagaStateEnum.PAYMENT_CHARGING)
        await session.commit()

        await logger.ainfo(
            "Inventory reserved → PAYMENT_CHARGING",
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
        )
        await producer.send_command(
            topic=broker_cfg.kafka_topic_payment_commands,
            command_type=EventTypeEnum.CHARGE_PAYMENT,
            saga_id=saga.saga_id,
            order_id=saga.order_id,
            payload=saga.inventory_command_payload,
        )


class HandlePaymentSucceeded(HandlerFunc):
    """Payment succeeded — complete the saga."""

    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None:
        assert saga is not None

        await dao.reset_retry_count(session, saga)
        await dao.update_state(session, saga, SagaStateEnum.COMPLETED)
        await session.commit()

        await logger.ainfo(
            "Payment succeeded → COMPLETED",
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
        )
        publisher = EventPublisher(
            producer=producer, broker_cfg=broker_cfg, dao=dao, retry_cfg=retry_cfg
        )
        await publisher.publish_saga_completed(saga)


class HandleReservationCancelled(HandlerFunc):
    """Inventory reservation cancelled — compensate and cancel the saga."""

    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None:
        assert saga is not None

        await dao.reset_retry_count(session, saga)
        await dao.update_state(session, saga, SagaStateEnum.CANCELLED)
        await session.commit()

        await logger.ainfo(
            "Inventory reservation cancelled → CANCELLED (compensation complete)",
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
        )
        publisher = EventPublisher(
            producer=producer, broker_cfg=broker_cfg, dao=dao, retry_cfg=retry_cfg
        )
        await publisher.publish_saga_cancelled(saga)


class HandleFailure(HandlerFunc):
    """Universal failure handler — schedules retry or sends to DLQ."""

    async def __call__(
        self,
        session: AsyncSession,
        saga: SagaState | None,
        event: IncomingEvent,
        *,
        producer: KafkaProducerClient,
        dao: SagaStateDAO,
        broker_cfg: BrokerSettings,
        retry_cfg: RetrySettings,
    ) -> None:
        assert saga is not None
        error: str = getattr(event, "error", event.event_type)
        await logger.awarning(
            "Event failure – scheduling retry or DLQ",
            event_type=event.event_type,
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
            retry_count=saga.retry_count,
        )
        publisher = EventPublisher(
            producer=producer, broker_cfg=broker_cfg, dao=dao, retry_cfg=retry_cfg
        )
        await publisher.schedule_retry_or_dlq(session, saga, error, event)


handle_order_created = HandleOrderCreated()
handle_order_created_duplicate = HandleOrderCreatedDuplicate()
handle_inventory_reserved = HandleInventoryReserved()
handle_payment_succeeded = HandlePaymentSucceeded()
handle_reservation_cancelled = HandleReservationCancelled()
handle_failure = HandleFailure()
