import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.common.dto import BaseResponseDTO
from app.common.enums import OrderStatusEnum


class OrderResponseDTO(BaseResponseDTO):
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatusEnum
    items: Any
    total_amount: Decimal
    currency: str
    saga_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CreateOrderResponseDTO(BaseResponseDTO):
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatusEnum
    items: Any
    total_amount: Decimal
    currency: str
    saga_id: uuid.UUID | None
    created_at: datetime
