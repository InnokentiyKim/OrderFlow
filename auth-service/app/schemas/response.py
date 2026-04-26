from datetime import datetime

from app.common.dto import BaseResponseDTO, BaseDTO
from app.schemas.result import UserInfo


class RegisterUserResponseDTO(BaseResponseDTO):
    email: str
    role: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    @classmethod
    def from_model(cls, model: "UserInfo") -> "RegisterUserResponseDTO":
        return cls(
            id=model.id,
            email=model.email,
            role=model.role,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_active=model.is_active,
        )


class LoginUserResponseDTO(BaseDTO):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutUserResponseDTO(BaseDTO):
    message: str = "Successfully logged out"


class AuthTokensResponseDTO(LoginUserResponseDTO): ...


class UserInfoResponseDTO(BaseResponseDTO):
    email: str
    role: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    @classmethod
    def from_model(cls, model: "UserInfo") -> "UserInfoResponseDTO":
        return cls(
            id=model.id,
            email=model.email,
            role=model.role,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_active=model.is_active,
        )
