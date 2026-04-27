from enum import StrEnum


class OrderStatusEnum(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CurrencyEnum(StrEnum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"


class AuthTokenTypeEnum(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
