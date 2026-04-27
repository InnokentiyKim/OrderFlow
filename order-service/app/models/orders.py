import uuid
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy import DECIMAL, TIMESTAMP, String, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.common.model import Base
from app.common.enums import OrderStatusEnum


class OrderBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class Order(OrderBase):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[OrderStatusEnum] = mapped_column(
        SAEnum(OrderStatusEnum), nullable=False
    )
    items: Mapped[list] = mapped_column(JSONB, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    saga_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    def __init__(
        self,
        user_id: uuid.UUID,
        status: OrderStatusEnum,
        items: list,
        total_amount: Decimal,
        currency: str,
        saga_id: uuid.UUID | None = None,
    ):
        self.id = uuid.uuid4()
        self.user_id = user_id
        self.status = status
        self.items = items
        self.total_amount = total_amount
        self.currency = currency
        self.saga_id = saga_id

        now = datetime.now(UTC)
        self.created_at = now
        self.updated_at = now

        super().__init__()

    @property
    def is_pending(self) -> bool:
        """Check if the order is in a pending state."""
        return self.status == OrderStatusEnum.PENDING

    @property
    def is_confirmed(self) -> bool:
        """Check if the order is in a confirmed state."""
        return self.status == OrderStatusEnum.CONFIRMED

    @property
    def is_completed(self) -> bool:
        """Check if the order is in a completed state."""
        return self.status == OrderStatusEnum.COMPLETED

    @property
    def is_cancelled(self) -> bool:
        """Check if the order is in a cancelled state."""
        return self.status == OrderStatusEnum.CANCELLED

    def set_status(self, status: OrderStatusEnum) -> None:
        """Update the order status and corresponding timestamps."""
        self.status = status
        self.updated_at = datetime.now(UTC)
