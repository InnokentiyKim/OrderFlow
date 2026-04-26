from typing import Annotated

from pydantic import Field, EmailStr, SecretStr
from app.common.dto import BaseRequestDTO
from app.common.enums import UserRoleEnum


class RegisterUserRequestDTO(BaseRequestDTO):
    email: Annotated[str, EmailStr] = Field(
        max_length=64, description="User's email address"
    )
    password: str = Field(min_length=4, max_length=64, description="User's password")
    role: UserRoleEnum = Field(default=UserRoleEnum.USER, description="User's role")
    is_active: bool = Field(default=True, description="User's is_active")


class LoginUserRequestDTO(BaseRequestDTO):
    email: Annotated[str, EmailStr]
    password: Annotated[str, SecretStr]


class LogoutUserRequestDTO(BaseRequestDTO):
    refresh_token: SecretStr


class RefreshSessionRequestDTO(BaseRequestDTO):
    refresh_token: SecretStr
