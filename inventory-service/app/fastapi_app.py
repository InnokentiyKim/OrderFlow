import asyncio
import hashlib
import json
import logging
import random
from contextlib import asynccontextmanager

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import settings
from app.health import router as health_router
from app.models import Command, CommandType, InventoryEvent

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def deterministic_roll(message_id: str) -> float:
    """Return float in [0, 1) deterministically seeded from message_id."""
    seed = int(hashlib.md5(message_id.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed).random()


async def publish_event(producer: AIOKafkaProducer, event: InventoryEvent) -> None:
    await producer.send_and_wait(
        settings.kafka_output_topic,
        value=event.to_kafka_bytes(),
        key=event.kafka_key(),
    )
    await logger.ainfo(
        "Published event",
        event_type=event.event_type,
        saga_id=event.saga_id,
        order_id=event.order_id,
        message_id=event.message_id,
    )


async def handle_command(
    cmd: Command,
    producer: AIOKafkaProducer,
    redis: Redis,
) -> None:
    idempotency_key = f"inventory:processed:{cmd.message_id}"
    if await redis.exists(idempotency_key):
        await logger.ainfo(
            "Duplicate command, skipping",
            message_id=cmd.message_id,
            command_type=cmd.command_type,
        )
        return

    match cmd.command_type:
        case CommandType.CANCEL_RESERVATION:
            event = InventoryEvent(
                event_type="inventory.reservation-cancelled",
                saga_id=cmd.saga_id,
                order_id=cmd.order_id,
                payload={"message": "Reservation cancelled"},
            )
            await publish_event(producer, event)

        case CommandType.RESERVE_INVENTORY:
            roll = deterministic_roll(cmd.message_id)
            if roll < 0.8:
                event = InventoryEvent(
                    event_type="inventory.reserved",
                    saga_id=cmd.saga_id,
                    order_id=cmd.order_id,
                    payload={
                        "message": "Inventory reserved successfully",
                        "items": cmd.payload.get("items", []),
                    },
                )
            else:
                event = InventoryEvent(
                    event_type="inventory.reserve-failed",
                    saga_id=cmd.saga_id,
                    order_id=cmd.order_id,
                    payload={
                        "message": "Inventory reservation failed",
                        "reason": "Insufficient stock",
                    },
                )
            await publish_event(producer, event)

        case _:
            await logger.awarn(
                "Unknown command_type",
                command_type=cmd.command_type,
                message_id=cmd.message_id,
            )
            return

    await redis.setex(idempotency_key, settings.idempotency_ttl, "1")


async def consume_loop(
    consumer: AIOKafkaConsumer,
    producer: AIOKafkaProducer,
    redis: Redis,
) -> None:
    await logger.ainfo("Starting consume loop", topic=settings.kafka_input_topic)
    async for msg in consumer:
        try:
            data = json.loads(msg.value)
            cmd = Command.model_validate(data)
            await logger.ainfo(
                "Received command",
                command_type=cmd.command_type,
                saga_id=cmd.saga_id,
                order_id=cmd.order_id,
                message_id=cmd.message_id,
            )
            await handle_command(cmd, producer, redis)
            await consumer.commit()
        except Exception as exc:
            await logger.aerror("Error processing message", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    await producer.start()

    consumer = AIOKafkaConsumer(
        settings.kafka_input_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        auto_offset_reset=settings.kafka_auto_offset_reset,
        enable_auto_commit=settings.kafka_enable_auto_commit,
    )
    await consumer.start()

    await logger.ainfo("All clients started")

    task = asyncio.create_task(consume_loop(consumer, producer, redis))

    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await consumer.stop()
        await producer.stop()
        await redis.aclose()
        await logger.ainfo("Graceful shutdown complete")


app = FastAPI(title="Inventory Service Stub", lifespan=lifespan)
app.include_router(health_router)
