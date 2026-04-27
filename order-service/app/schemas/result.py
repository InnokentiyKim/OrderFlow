import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.common.enums import OrderStatusEnum
from app.models.orders import Order


@dataclass(slots=True, frozen=True)
class GetOrderResult:
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatusEnum
    items: Any
    total_amount: Decimal
    currency: str
    saga_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, order: Order) -> "GetOrderResult":
        return cls(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            items=order.items,
            total_amount=order.total_amount,
            currency=order.currency,
            saga_id=order.saga_id,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )


@dataclass(slots=True, frozen=True)
class CreateOrderResult:
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatusEnum
    items: Any
    total_amount: Decimal
    currency: str
    saga_id: uuid.UUID | None
    created_at: datetime

    @classmethod
    def from_model(cls, order: Order) -> "CreateOrderResult":
        return cls(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            items=order.items,
            total_amount=order.total_amount,
            currency=order.currency,
            saga_id=order.saga_id,
            created_at=order.created_at,
        )


@dataclass(slots=True, frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    role: str  # "user" | "admin"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
