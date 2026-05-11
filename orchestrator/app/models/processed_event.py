import uuid
from datetime import datetime, UTC

from sqlalchemy import TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.saga_state import SagaStateBase


class ProcessedEvent(SagaStateBase):
    """Idempotency log: one row per processed Kafka event_id."""

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False
    )
    saga_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    def __init__(
        self,
        event_id: uuid.UUID,
        saga_id: uuid.UUID,
        event_type: str,
    ) -> None:
        self.event_id = event_id
        self.saga_id = saga_id
        self.event_type = event_type
        self.processed_at = datetime.now(UTC)

        super().__init__()
