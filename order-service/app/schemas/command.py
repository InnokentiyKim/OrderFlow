from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(slots=True, frozen=True)
class CreateOrderCommand:
    user_id: UUID
    items: list[Any]
    total_amount: Decimal
    currency: str
