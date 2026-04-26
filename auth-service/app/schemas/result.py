import uuid
from dataclasses import dataclass
from datetime import datetime
from pydantic import SecretStr

from app.common.enums import UserRoleEnum
from app.models.refresh_tokens import RefreshToken
from app.models.users import User


@dataclass(slots=True, frozen=True)
class UserID:
    id: uuid.UUID


@dataclass(slots=True, frozen=True)
class TokenPayload:
    user_id: uuid.UUID
    role: UserRoleEnum


@dataclass(slots=True, frozen=True)
class TokenInfo:
    id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoked: bool

    @classmethod
    def from_model(cls, model: "RefreshToken") -> "TokenInfo":
        return cls(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            issued_at=model.issued_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            revoked=model.revoked,
        )


@dataclass(slots=True, frozen=True)
class RefreshTokensResult:
    id: uuid.UUID


@dataclass(slots=True, frozen=True)
class AuthTokens:
    access_token: SecretStr
    refresh_token: SecretStr


@dataclass(slots=True, frozen=True)
class UserInfo:
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    @classmethod
    def from_model(cls, model: "User") -> "UserInfo":
        return cls(
            id=model.id,
            email=model.email,
            role=model.role,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_active=model.is_active,
        )
