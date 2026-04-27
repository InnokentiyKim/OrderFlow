import uuid
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GetOrderInfo:
    order_id: uuid.UUID
