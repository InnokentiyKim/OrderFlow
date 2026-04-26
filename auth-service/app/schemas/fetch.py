import uuid
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GetUserInfo:
    user_id: uuid.UUID
