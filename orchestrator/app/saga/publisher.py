import random
from datetime import datetime, UTC, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import EventTypeEnum, SagaStateEnum
from app.core.config import BrokerSettings, RetrySettings
from app.integrations.dao.saga import SagaStateDAO
from app.integrations.kafka_producer import KafkaProducerClient
from app.models.events import IncomingEvent
from app.models.saga_state import SagaState

logger = structlog.get_logger(__name__)


class EventPublisher:
    """Publishes saga outcomes and handles retry/DLQ logic. Used by handlers to emit results."""

    def __init__(
        self,
        producer: KafkaProducerClient,
        broker_cfg: BrokerSettings,
        dao: SagaStateDAO,
        retry_cfg: RetrySettings,
    ) -> None:
        self._producer = producer
        self._broker_cfg = broker_cfg
        self._dao = dao
        self._retry_cfg = retry_cfg

    async def publish_saga_completed(self, saga: SagaState) -> None:
        """Publishes a SAGA_COMPLETED event to the order events topic."""
        await self._producer.send_event(
            topic=self._broker_cfg.kafka_topic_order_events,
            event_type=EventTypeEnum.SAGA_COMPLETED,
            saga_id=saga.saga_id,
            order_id=saga.order_id,
            payload={"status": "COMPLETED"},
        )

    async def publish_saga_cancelled(self, saga: SagaState) -> None:
        """Publishes a SAGA_CANCELLED event to the order events topic."""
        await self._producer.send_event(
            topic=self._broker_cfg.kafka_topic_order_events,
            event_type=EventTypeEnum.SAGA_CANCELLED,
            saga_id=saga.saga_id,
            order_id=saga.order_id,
            payload={"status": "CANCELLED"},
        )

    async def publish_saga_failed(self, saga: SagaState) -> None:
        """Publishes a SAGA_FAILED event to the order events topic."""
        await self._producer.send_event(
            topic=self._broker_cfg.kafka_topic_order_events,
            event_type=EventTypeEnum.SAGA_FAILED,
            saga_id=saga.saga_id,
            order_id=saga.order_id,
            payload={"status": "FAILED", "retry_count": saga.retry_count},
        )

    async def schedule_retry_or_dlq(
        self,
        session: AsyncSession,
        saga: SagaState,
        error: str,
        event: IncomingEvent,
    ) -> bool:
        """Increments retry count and either schedules a retry with backoff or sends to DLQ if max retries exceeded."""
        await self._dao.increment_retry(session, saga)

        if saga.retry_count <= self._retry_cfg.saga_max_retries:
            backoff = self._calc_backoff(saga.retry_count)
            retry_after = datetime.now(UTC) + timedelta(seconds=backoff)
            await self._dao.set_retry_after(
                session, saga, retry_after, last_error=error
            )
            await session.commit()
            await logger.awarning(
                "Scheduled retry",
                saga_id=str(saga.saga_id),
                order_id=str(saga.order_id),
                current_state=saga.state,
                retry_count=saga.retry_count,
                backoff_seconds=round(backoff, 2),
                retry_after=retry_after.isoformat(),
            )
            return True

        original_state = saga.state.value
        await self._dao.update_state(session, saga, SagaStateEnum.FAILED)
        await session.commit()

        await self._producer.send_to_dlq(
            topic=self._broker_cfg.kafka_topic_dlq,
            saga_id=saga.saga_id,
            order_id=saga.order_id,
            original_state=original_state,
            retry_count=saga.retry_count,
            last_error=error,
            original_event=event.model_dump(mode="json"),
        )
        await self.publish_saga_failed(saga)

        await logger.aerror(
            "Max retries exhausted → DLQ + FAILED",
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
            original_state=original_state,
            retry_count=saga.retry_count,
            last_error=error,
        )
        return False

    def _calc_backoff(self, attempt: int) -> float:
        base = self._retry_cfg.saga_retry_base_backoff**attempt
        jitter = base * self._retry_cfg.saga_retry_jitter * random.uniform(-1, 1)
        return max(0.1, base + jitter)
