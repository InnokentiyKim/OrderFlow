from dataclasses import dataclass
from uuid import UUID
from pydantic import SecretStr
from app.common.enums import UserRoleEnum, AuthTokenTypeEnum


@dataclass(slots=True, frozen=True)
class VerifyUserByTokenCommand:
    token: SecretStr
    token_type: AuthTokenTypeEnum


@dataclass(slots=True, frozen=True)
class Authorize:
    user_role: UserRoleEnum


@dataclass(slots=True, frozen=True)
class CreateAuthSessionCommand:
    user_id: UUID
    role: str


@dataclass(slots=True, frozen=True)
class InvalidateRefreshTokenCommand:
    refresh_token: SecretStr
    user_id: UUID


@dataclass(slots=True, frozen=True)
class LoginUserCommand:
    email: str
    password: SecretStr


@dataclass(slots=True, frozen=True)
class CreateUserCommand:
    email: str
    password: SecretStr
    role: UserRoleEnum
    is_active: bool | None


@dataclass(slots=True, frozen=True)
class VerifyUserCredentialsCommand:
    email: str
    password: SecretStr
