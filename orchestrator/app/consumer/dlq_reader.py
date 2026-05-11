import asyncio
import json

import structlog
from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from app.core.config import app_config
from app.models.events import DLQEvent

logger = structlog.get_logger(__name__)


async def run_dlq_reader(shutdown_event: asyncio.Event) -> None:
    cfg = app_config.broker

    consumer = AIOKafkaConsumer(
        cfg.kafka_topic_dlq,
        bootstrap_servers=cfg.kafka_bootstrap_servers,
        group_id=f"{cfg.kafka_consumer_group}.dlq-reader",
        auto_offset_reset=cfg.kafka_auto_offset_reset,
        enable_auto_commit=cfg.kafka_auto_commit,
    )

    await consumer.start()
    await logger.ainfo(
        "DLQ reader started",
        topic=cfg.kafka_topic_dlq,
        group_id=f"{cfg.kafka_consumer_group}.dlq-reader",
    )

    try:
        while not shutdown_event.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            if not batch:
                continue
            for _tp, messages in batch.items():
                for msg in messages:
                    await _handle_dlq_message(msg)
    finally:
        await consumer.stop()
        await logger.ainfo("consumer stopped")


async def _handle_dlq_message(msg: object) -> None:
    try:
        data = json.loads(msg.value)  # type: ignore[union-attr]
        event = DLQEvent.from_kafka_message(data)

        await logger.aerror(
            "DLQ event received – saga permanently failed",
            saga_id=str(event.saga_id),
            order_id=str(event.order_id),
            original_state=event.original_state,
            retry_count=event.retry_count,
            last_error=event.last_error,
            failed_at=event.failed_at.isoformat() if event.failed_at else None,
            partition=msg.partition,  # type: ignore[union-attr]
            offset=msg.offset,  # type: ignore[union-attr]
        )
    except (ValidationError, Exception) as exc:
        await logger.aerror(
            "DLQ reader: failed to parse message",
            error=str(exc),
            raw=getattr(msg, "value", None),
        )
