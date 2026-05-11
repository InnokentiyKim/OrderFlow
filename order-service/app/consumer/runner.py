import asyncio
import json
import uuid
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.enums import OrderStatusEnum
from app.core.config import app_config
from app.integrations.cache import OrderCache
from app.integrations.dao.order import OrderDAO
from app.integrations.redis_client import RedisClient

logger = structlog.get_logger(__name__)

# Map saga event types → final order statuses
_STATUS_MAP: dict[str, OrderStatusEnum] = {
    "saga.completed": OrderStatusEnum.COMPLETED,
    "saga.cancelled": OrderStatusEnum.CANCELLED,
}


async def run_cache_consumer(
    redis: RedisClient,
    session_factory: async_sessionmaker[AsyncSession],
    shutdown_event: asyncio.Event,
) -> None:
    """Long-running consumer task; should be started as asyncio.create_task()."""
    cfg = app_config.broker
    order_cache = OrderCache(redis)
    dao = OrderDAO()

    consumer = AIOKafkaConsumer(
        cfg.kafka_topic_order_events,
        bootstrap_servers=cfg.kafka_bootstrap_servers,
        group_id=cfg.cache_group_id,
        auto_offset_reset=cfg.kafka_auto_offset_reset,
        enable_auto_commit=cfg.kafka_enable_auto_commit,
    )

    try:
        await consumer.start()
    except Exception as exc:
        await logger.aerror(
            "Cache invalidation consumer failed to start – skipping cache invalidation",
            error=str(exc),
        )
        return

    await logger.ainfo(
        "Cache invalidation consumer started",
        topic=cfg.kafka_topic_order_events,
        group_id=cfg.cache_group_id,
    )

    try:
        while not shutdown_event.is_set():
            async for msg in consumer:
                try:
                    await _handle_message(
                        consumer, msg, order_cache, dao, session_factory
                    )
                except Exception as exc:
                    await logger.aerror(
                        "Cache consumer: unhandled error in message handler",
                        error=str(exc),
                        offset=msg.offset,
                    )
    except asyncio.CancelledError:
        await logger.ainfo("Cache invalidation consumer cancelled")
    finally:
        try:
            await consumer.stop()
        except Exception as exc:
            await logger.awarning("Cache consumer stop error (ignored)", error=str(exc))
        await logger.ainfo("Cache invalidation consumer stopped")


def _parse_message(msg: Any) -> dict[str, Any] | None:
    """Parse the Kafka message value as JSON. If parsing fails, return None to indicate an invalid message."""
    try:
        return json.loads(msg.value)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


async def _handle_message(
    consumer: AIOKafkaConsumer,
    msg: Any,
    order_cache: OrderCache,
    dao: OrderDAO,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Process a single Kafka message: parse it, determine if it's a saga outcome event,
    update DB and invalidate cache if needed, and commit offset.

    Any exceptions are logged and cause the message to be retried (offset not committed).
    """
    data = _parse_message(msg)
    if data is None:
        await logger.awarning(
            "Cache consumer: malformed message, skipping",
            offset=msg.offset,
        )
        await consumer.commit()
        return

    try:
        event_type: str = data.get("event_type", "")
        new_status = _STATUS_MAP.get(event_type)
        order_id = uuid.UUID(str(data["order_id"])) if new_status else None
    except (KeyError, ValueError, AttributeError) as exc:
        await logger.awarning(
            "Cache consumer: invalid message fields, skipping",
            error=str(exc),
            offset=msg.offset,
        )
        await consumer.commit()
        return

    if new_status is None:
        # Not a saga outcome event – skip silently, commit offset
        await consumer.commit()
        return

    try:
        async with session_factory() as session:
            async with session.begin():
                await dao.update_order_status(session, order_id, new_status)
    except Exception as exc:
        await logger.aerror(
            "Cache consumer: DB update failed – offset NOT committed, will retry",
            order_id=str(order_id),
            error=str(exc),
        )
        return  # Do not commit – message will be redelivered

    await order_cache.invalidate(order_id)

    await consumer.commit()
    await logger.ainfo(
        "Cache consumer: processed saga outcome",
        event_type=event_type,
        order_id=str(order_id),
        new_status=new_status,
        offset=msg.offset,
    )
