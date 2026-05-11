import uuid
from datetime import datetime, UTC

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processed_event import ProcessedEvent


class ProcessedEventDAO:
    @staticmethod
    async def try_insert(
        session: AsyncSession,
        event_id: uuid.UUID,
        saga_id: uuid.UUID,
        event_type: str,
    ) -> bool:
        """Try to insert a new ProcessedEvent. Returns True if inserted, False if already exists."""
        stmt = (
            insert(ProcessedEvent)
            .values(
                event_id=event_id,
                saga_id=saga_id,
                event_type=event_type,
                processed_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        result = await session.execute(stmt)
        return result.rowcount == 1
