import asyncio
from typing import Any

import structlog
from datetime import datetime, UTC
from app.common.enums import EventTypeEnum, SagaStateEnum
from app.core.config import app_config
from app.integrations.dao.saga import SagaStateDAO
from app.integrations.kafka_producer import KafkaProducerClient
from app.models.saga_state import SagaState

logger = structlog.get_logger(__name__)


def _build_state_command_map(
    cfg: Any,
) -> dict[SagaStateEnum, tuple[EventTypeEnum, str]]:
    broker = cfg.broker
    return {
        SagaStateEnum.INVENTORY_RESERVING: (
            EventTypeEnum.RESERVE_INVENTORY,
            broker.kafka_topic_inventory_commands,
        ),
        SagaStateEnum.PAYMENT_CHARGING: (
            EventTypeEnum.CHARGE_PAYMENT,
            broker.kafka_topic_payment_commands,
        ),
        SagaStateEnum.COMPENSATING_INVENTORY: (
            EventTypeEnum.CANCEL_RESERVATION,
            broker.kafka_topic_inventory_commands,
        ),
    }


def _build_payload(state: SagaStateEnum, saga: SagaState) -> dict[str, Any]:
    if state == SagaStateEnum.INVENTORY_RESERVING:
        return saga.order_command_payload
    if state == SagaStateEnum.PAYMENT_CHARGING:
        return saga.inventory_command_payload

    return {}


async def recover_stuck_sagas(session_factory: Any) -> None:
    """Called once on startup to reschedule sagas that were left mid-flight.

    If the orchestrator crashed after committing the DB state but before
    committing the Kafka offset (or before sending the command), those sagas
    remain in a non-terminal state with retry_after=NULL, invisible to the
    regular retry worker.  This function sets retry_after=now so the retry
    worker picks them up on its first tick.
    """
    dao = SagaStateDAO()
    now = datetime.now(UTC)

    async with session_factory() as session:
        stuck = await dao.get_stuck_active_sagas(session)

        if not stuck:
            await logger.ainfo("Startup recovery: no stuck sagas found")
            return

        for saga in stuck:
            saga.retry_after = now
            saga.updated_at = now

        await session.commit()

    await logger.awarning(
        "Startup recovery: rescheduled stuck sagas",
        count=len(stuck),
        saga_ids=[str(s.saga_id) for s in stuck],
    )


async def run_retry_worker(
    producer: KafkaProducerClient,
    session_factory: Any,
    poll_interval: float = 1.0,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    """Long-running task: every poll_interval seconds check for due retries."""
    cfg = app_config
    dao = SagaStateDAO()
    _state_command = _build_state_command_map(cfg)
    _event = shutdown_event or asyncio.Event()

    await logger.ainfo("Retry worker started", poll_interval=poll_interval)

    while not _event.is_set():
        try:
            await asyncio.sleep(poll_interval)
            async with session_factory() as session:
                pending = await dao.get_pending_retries(session)

            for saga in pending:
                await _fire_retry(producer, session_factory, dao, _state_command, saga)

        except asyncio.CancelledError:
            await logger.ainfo("Retry worker cancelled")
            return
        except Exception as exc:
            await logger.aerror(
                "Retry worker unexpected error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    await logger.ainfo("consumer stopped")


async def _fire_retry(
    producer: KafkaProducerClient,
    session_factory: Any,
    dao: SagaStateDAO,
    state_command: dict[SagaStateEnum, tuple[EventTypeEnum, str]],
    saga: SagaState,
) -> None:
    state = saga.state
    entry = state_command.get(state)

    if entry is None:
        await logger.awarning(
            "Retry worker: no command mapping for state, clearing retry_after",
            saga_id=str(saga.saga_id),
            state=state,
        )
        async with session_factory() as session:
            fresh = await dao.get_by_saga_id(session, saga.saga_id)
            if fresh:
                await dao.clear_retry_after(session, fresh)
                await session.commit()
        return

    command_type: EventTypeEnum
    topic: str
    command_type, topic = entry
    payload = _build_payload(state, saga)

    try:
        # Clear retry_after BEFORE sending to avoid duplicate sends on failure
        async with session_factory() as session:
            fresh = await dao.get_by_saga_id(session, saga.saga_id)
            if fresh is None or fresh.retry_after is None:
                # Already handled by another worker instance or cleared
                return
            await dao.clear_retry_after(session, fresh)
            await session.commit()

        await producer.send_command(
            topic=topic,
            command_type=command_type,
            saga_id=saga.saga_id,
            order_id=saga.order_id,
            payload=payload,
        )

        await logger.awarning(
            "Retry worker: re-sent command",
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
            state=state,
            command_type=command_type,
            retry_count=saga.retry_count,
        )

    except Exception as exc:
        await logger.aerror(
            "Retry worker: failed to re-send command",
            saga_id=str(saga.saga_id),
            order_id=str(saga.order_id),
            error=str(exc),
        )
