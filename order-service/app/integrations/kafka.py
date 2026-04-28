import json
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from app.core.config import app_config

logger = structlog.get_logger(__name__)


class KafkaProducerClient:
    """A wrapper around AIOKafkaProducer that provides structured logging and error handling."""
    def __init__(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=app_config.broker.kafka_bootstrap_servers,
            acks=app_config.broker.kafka_acks,
            enable_idempotence=app_config.broker.kafka_enable_idempotence,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
        )

    async def start(self) -> None:
        """Start the Kafka producer; must be called before sending messages."""
        await self._producer.start()
        await logger.ainfo("Kafka producer started")

    async def stop(self) -> None:
        """Stop the Kafka producer; should be called during application shutdown."""
        await self._producer.stop()
        await logger.ainfo("Kafka producer stopped")

    async def send(self, topic: str, value: Any, key: str | None = None) -> None:
        """Send a message; never raises – logs error instead."""
        try:
            await self._producer.send_and_wait(topic, value=value, key=key)
        except Exception as exc:
            await logger.aerror(
                "Kafka send failed",
                topic=topic,
                key=key,
                error=str(exc),
                error_type=type(exc).__name__,
            )


def provide_kafka_producer() -> KafkaProducerClient:
    """Dependency provider for KafkaProducerClient."""
    return KafkaProducerClient()
