import uuid
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import SagaStateEnum
from app.models.saga_state import SagaState


class SagaStateDAO:
    @staticmethod
    async def get_by_saga_id(
        session: AsyncSession, saga_id: uuid.UUID
    ) -> SagaState | None:
        result = await session.execute(
            select(SagaState).where(SagaState.saga_id == saga_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, saga: SagaState) -> SagaState:
        session.add(saga)
        await session.flush()
        return saga

    @staticmethod
    async def update_state(
        session: AsyncSession,
        saga: SagaState,
        new_state: SagaStateEnum,
    ) -> SagaState:
        saga.state = new_state
        saga.updated_at = datetime.now(UTC)
        await session.flush()
        return saga

    @staticmethod
    async def increment_retry(session: AsyncSession, saga: SagaState) -> SagaState:
        saga.retry_count += 1
        saga.updated_at = datetime.now(UTC)
        await session.flush()
        return saga

    @staticmethod
    async def reset_retry_count(session: AsyncSession, saga: SagaState) -> SagaState:
        saga.retry_count = 0
        saga.retry_after = None
        saga.last_error = None
        saga.updated_at = datetime.now(UTC)
        await session.flush()
        return saga

    @staticmethod
    async def set_retry_after(
        session: AsyncSession,
        saga: SagaState,
        retry_after: datetime,
        last_error: Optional[str] = None,
    ) -> SagaState:
        saga.retry_after = retry_after
        if last_error is not None:
            saga.last_error = last_error
        saga.updated_at = datetime.now(UTC)
        await session.flush()
        return saga

    @staticmethod
    async def clear_retry_after(session: AsyncSession, saga: SagaState) -> SagaState:
        saga.retry_after = None
        saga.updated_at = datetime.now(UTC)
        await session.flush()
        return saga

    @staticmethod
    async def get_pending_retries(session: AsyncSession) -> list[SagaState]:
        """Return sagas with retry_after <= now (ready to be retried)."""
        now = datetime.now(UTC)
        result = await session.execute(
            select(SagaState).where(
                SagaState.retry_after.isnot(None),
                SagaState.retry_after <= now,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_stuck_active_sagas(session: AsyncSession) -> list[SagaState]:
        """Return non-terminal sagas that have no retry_after scheduled.

        These are sagas that were left mid-flight after a crash: the DB state was
        committed but the Kafka command was never sent (or the offset was never
        committed), so the retry worker cannot pick them up on its own.
        """
        from app.common.enums import (
            SagaStateEnum,
        )

        terminal_states = [
            SagaStateEnum.COMPLETED,
            SagaStateEnum.CANCELLED,
            SagaStateEnum.FAILED,
        ]
        result = await session.execute(
            select(SagaState).where(
                SagaState.state.notin_(terminal_states),
                SagaState.retry_after.is_(None),
            )
        )
        return list(result.scalars().all())
