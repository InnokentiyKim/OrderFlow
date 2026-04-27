from decimal import Decimal

from pydantic import Field, field_validator

from app.common.dto import BaseRequestDTO
from app.common.enums import CurrencyEnum


class OrderItemDTO(BaseRequestDTO):
    product_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, max_digits=15, decimal_places=4)


class OrderCreateRequestDTO(BaseRequestDTO):
    items: list[OrderItemDTO] = Field(min_length=1)
    currency: CurrencyEnum = Field(default=CurrencyEnum.USD)

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("items must not be empty")
        return v
