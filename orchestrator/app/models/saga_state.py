import uuid
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import TIMESTAMP, Integer, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model import Base
from app.common.enums import SagaStateEnum


class SagaStateBase(Base):
    __abstract__ = True


class SagaState(SagaStateBase):
    __tablename__ = "saga_state"

    saga_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    state: Mapped[SagaStateEnum] = mapped_column(
        SAEnum(SagaStateEnum, name="sagastateenum"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_after: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    def __init__(
        self,
        saga_id: uuid.UUID,
        order_id: uuid.UUID,
        state: SagaStateEnum,
        payload: dict,
    ) -> None:
        now = datetime.now(UTC)
        self.saga_id = saga_id
        self.order_id = order_id
        self.state = state
        self.payload = payload
        self.retry_count = 0
        self.retry_after = None
        self.last_error = None
        self.created_at = now
        self.updated_at = now

        super().__init__()

    @property
    def order_command_payload(self) -> dict:
        """Convert the saga state to a payload for Kafka commands."""
        return {"items": self.payload.get("items", [])}

    @property
    def inventory_command_payload(self) -> dict:
        """Convert the saga state to a payload for inventory commands."""
        return {
            "amount": self.payload.get("total_amount"),
            "currency": self.payload.get("currency", "USD"),
        }
