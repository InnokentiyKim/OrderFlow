from enum import StrEnum


class SagaStateEnum(StrEnum):
    CREATED = "CREATED"
    INVENTORY_RESERVING = "INVENTORY_RESERVING"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    PAYMENT_CHARGING = "PAYMENT_CHARGING"
    COMPLETED = "COMPLETED"
    COMPENSATING_INVENTORY = "COMPENSATING_INVENTORY"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            SagaStateEnum.COMPLETED,
            SagaStateEnum.CANCELLED,
            SagaStateEnum.FAILED,
        )


class EventTypeEnum(StrEnum):
    # Входящие события
    ORDER_CREATED = "order.created"
    INVENTORY_RESERVED = "inventory.reserved"
    INVENTORY_RESERVE_FAILED = "inventory.reserve-failed"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    INVENTORY_RESERVATION_CANCELLED = "inventory.reservation-cancelled"
    INVENTORY_RESERVATION_CANCEL_FAILED = "inventory.reservation-cancel-failed"

    # Исходящие события саги
    SAGA_COMPLETED = "saga.completed"
    SAGA_CANCELLED = "saga.cancelled"
    SAGA_FAILED = "saga.failed"

    # Исходящие команды
    RESERVE_INVENTORY = "reserve_inventory"
    CHARGE_PAYMENT = "charge_payment"
    CANCEL_RESERVATION = "cancel_reservation"

    # Dead Letter Queue
    DLQ_EVENT = "dlq.event"
