from fastapi import APIRouter

from app.common.enums import AuthTokenTypeEnum
from app.schemas import command as commands
from pydantic import SecretStr
from app.schemas.request import (
    RegisterUserRequestDTO,
    LoginUserRequestDTO,
    RefreshSessionRequestDTO,
    LogoutUserRequestDTO,
)
from app.schemas.response import (
    RegisterUserResponseDTO,
    LoginUserResponseDTO,
    AuthTokensResponseDTO,
    LogoutUserResponseDTO,
    UserInfoResponseDTO,
)
from app.services.authentication import AuthServiceDependency
from app.services.user import UserServiceDependency
from app.common.auth_scheme import auth_header


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.post("/register", response_model=RegisterUserResponseDTO)
async def register_user(
    dto: RegisterUserRequestDTO, service: UserServiceDependency
) -> RegisterUserResponseDTO:
    user_info = await service.create_new_user(
        cmd=commands.CreateUserCommand(
            email=str(dto.email),
            password=SecretStr(dto.password),
            role=dto.role,
            is_active=dto.is_active,
        )
    )

    return RegisterUserResponseDTO.from_model(user_info)


@router.post("/login", response_model=LoginUserResponseDTO)
async def login_user(
    dto: LoginUserRequestDTO,
    auth_service: AuthServiceDependency,
    user_service: UserServiceDependency,
) -> LoginUserResponseDTO:
    cmd = commands.LoginUserCommand(email=dto.email, password=SecretStr(dto.password))

    user_info = await user_service.verify_user_credentials(
        cmd=commands.VerifyUserCredentialsCommand(
            email=cmd.email,
            password=cmd.password,
        )
    )

    auth_tokens = await auth_service.create_auth_session(
        cmd=commands.CreateAuthSessionCommand(user_id=user_info.id, role=user_info.role)
    )

    return LoginUserResponseDTO(
        access_token=auth_tokens.access_token.get_secret_value(),
        refresh_token=auth_tokens.refresh_token.get_secret_value(),
    )


@router.post("/refresh", response_model=AuthTokensResponseDTO)
async def refresh_session(
    dto: RefreshSessionRequestDTO,
    auth_service: AuthServiceDependency,
) -> AuthTokensResponseDTO:
    user_info = await auth_service.verify_user_by_token(
        cmd=commands.VerifyUserByTokenCommand(
            token=dto.refresh_token, token_type=AuthTokenTypeEnum.REFRESH
        )
    )

    # Generate new auth tokens
    auth_tokens = await auth_service.create_auth_session(
        cmd=commands.CreateAuthSessionCommand(user_id=user_info.id, role=user_info.role)
    )

    # Revoke the old refresh token
    await auth_service.invalidate_refresh_token(
        cmd=commands.InvalidateRefreshTokenCommand(
            refresh_token=dto.refresh_token,
            user_id=user_info.id,
        )
    )

    return AuthTokensResponseDTO(
        access_token=auth_tokens.access_token.get_secret_value(),
        refresh_token=auth_tokens.refresh_token.get_secret_value(),
    )


@router.post("/logout", response_model=LogoutUserResponseDTO)
async def logout_user(
    dto: LogoutUserRequestDTO,
    auth_service: AuthServiceDependency,
) -> LogoutUserResponseDTO:
    user_info = await auth_service.verify_user_by_token(
        cmd=commands.VerifyUserByTokenCommand(
            token=dto.refresh_token, token_type=AuthTokenTypeEnum.REFRESH
        )
    )

    # Revoke refresh token
    await auth_service.invalidate_refresh_token(
        cmd=commands.InvalidateRefreshTokenCommand(
            refresh_token=dto.refresh_token,
            user_id=user_info.id,
        )
    )

    return LogoutUserResponseDTO()


@router.post("/me", response_model=UserInfoResponseDTO)
async def get_user_info(
    auth_service: AuthServiceDependency,
    token: str = auth_header,
) -> UserInfoResponseDTO:
    user_info = await auth_service.verify_user_by_token(
        cmd=commands.VerifyUserByTokenCommand(
            token=SecretStr(token), token_type=AuthTokenTypeEnum.ACCESS
        )
    )

    return UserInfoResponseDTO.from_model(user_info)
