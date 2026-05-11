import asyncio
import json
import uuid
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from app.core.config import app_config
from app.integrations.dao.processed_event import ProcessedEventDAO
from app.integrations.database import get_session_factory
from app.integrations.kafka_producer import KafkaProducerClient
from app.models.events import parse_incoming_event
from app.saga.orchestrator import SagaOrchestrator
from app.common.enums import EventTypeEnum

logger = structlog.get_logger(__name__)


_INCOMING_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventTypeEnum.ORDER_CREATED,
        EventTypeEnum.INVENTORY_RESERVED,
        EventTypeEnum.INVENTORY_RESERVE_FAILED,
        EventTypeEnum.PAYMENT_SUCCEEDED,
        EventTypeEnum.PAYMENT_FAILED,
        EventTypeEnum.INVENTORY_RESERVATION_CANCELLED,
        EventTypeEnum.INVENTORY_RESERVATION_CANCEL_FAILED,
    }
)


async def run_consumer(
    producer: KafkaProducerClient, shutdown_event: asyncio.Event
) -> None:
    """Main consumer loop: consume events from Kafka, parse and validate them, check for duplicates,
    and dispatch to the orchestrator.
    """
    cfg = app_config.broker
    orchestrator = SagaOrchestrator(producer=producer)
    session_factory = get_session_factory()
    processed_event_dao = ProcessedEventDAO()

    consumer = AIOKafkaConsumer(
        cfg.kafka_topic_order_events,
        bootstrap_servers=cfg.kafka_bootstrap_servers,
        group_id=cfg.kafka_consumer_group,
        auto_offset_reset=cfg.kafka_auto_offset_reset,
        enable_auto_commit=False,
    )

    await consumer.start()
    await logger.ainfo(
        "Kafka consumer started",
        topic=cfg.kafka_topic_order_events,
        group_id=cfg.kafka_consumer_group,
    )

    try:
        while not shutdown_event.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            if not batch:
                continue
            await logger.ainfo("processing remaining events")
            for _tp, messages in batch.items():
                for msg in messages:
                    await _process_message(
                        consumer,
                        orchestrator,
                        producer,
                        session_factory,
                        msg,
                        processed_event_dao,
                    )
    finally:
        await consumer.commit()
        await consumer.stop()
        await logger.ainfo("consumer stopped")


async def _parse_message(
    consumer: AIOKafkaConsumer,
    producer: KafkaProducerClient,
    msg: Any,
) -> Any | None:
    """Parse and validate the incoming Kafka message. If invalid, send to DLQ and return None."""
    cfg = app_config.broker

    try:
        data: dict[str, Any] = json.loads(msg.value)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        await logger.aerror(
            "Invalid message format – sending to DLQ immediately",
            error=str(exc),
            partition=msg.partition,
            offset=msg.offset,
        )
        await producer.send_to_dlq(
            topic=cfg.kafka_topic_dlq,
            saga_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            original_state="UNKNOWN",
            retry_count=0,
            last_error=f"JSON decode error: {exc}",
            original_event={"raw": msg.value.decode("utf-8", errors="replace")},
        )
        await consumer.commit()
        return None

    event_type = data.get("event_type")
    if event_type not in _INCOMING_EVENT_TYPES:
        await logger.adebug(
            "Skipping non-incoming event type",
            event_type=event_type,
            partition=msg.partition,
            offset=msg.offset,
        )
        await consumer.commit()
        return None

    try:
        incoming_event = parse_incoming_event(data)
        return incoming_event
    except (ValidationError, Exception) as exc:
        await logger.aerror(
            "Invalid event schema – sending to DLQ immediately",
            error=str(exc),
            partition=msg.partition,
            offset=msg.offset,
        )

        await producer.send_to_dlq(
            topic=cfg.kafka_topic_dlq,
            saga_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            original_state="UNKNOWN",
            retry_count=0,
            last_error=f"Schema validation error: {exc}",
            original_event={"raw": msg.value.decode("utf-8", errors="replace")},
        )

        await consumer.commit()
        return None


async def _process_message(
    consumer: AIOKafkaConsumer,
    orchestrator: SagaOrchestrator,
    producer: KafkaProducerClient,
    session_factory: Any,
    msg: Any,
    processed_event_dao: ProcessedEventDAO,
) -> None:
    """Process a single Kafka message: parse, check for duplicates, and dispatch to orchestrator if new."""
    event_obj = await _parse_message(consumer, producer, msg)
    if event_obj is None:
        return

    event_type: str = event_obj.event_type
    saga_id_uuid: uuid.UUID = event_obj.saga_id
    event_id: uuid.UUID = getattr(event_obj, "event_id", uuid.uuid4())

    await logger.ainfo(
        "Received event",
        event_type=event_type,
        saga_id=str(saga_id_uuid),
        event_id=str(event_id),
        partition=msg.partition,
        offset=msg.offset,
    )

    async with session_factory() as session:
        inserted = await processed_event_dao.try_insert(
            session=session,
            event_id=event_id,
            saga_id=saga_id_uuid,
            event_type=event_type,
        )
        if not inserted:
            await logger.awarning(
                "Duplicate event, skipped",
                event_id=str(event_id),
                event_type=event_type,
                saga_id=str(saga_id_uuid),
                partition=msg.partition,
                offset=msg.offset,
            )
            await session.commit()
            await consumer.commit()
            return

        try:
            await orchestrator.handle_event(session, event_obj)
        except Exception as exc:
            # The DB state may or may not have been committed inside the handler.
            # Do NOT commit the offset – on restart the message will be re-delivered
            # and recover_stuck_sagas will reschedule any stuck sagas.
            await logger.aerror(
                "Unhandled error in orchestrator.handle_event – offset not committed",
                error=str(exc),
                error_type=type(exc).__name__,
                event_type=event_type,
                saga_id=str(saga_id_uuid),
                partition=msg.partition,
                offset=msg.offset,
            )
            return

    await consumer.commit()
    await logger.ainfo(
        "Offset committed",
        event_type=event_type,
        event_id=str(event_id),
        saga_id=str(saga_id_uuid),
        partition=msg.partition,
        offset=msg.offset,
    )
