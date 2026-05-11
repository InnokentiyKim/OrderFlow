from datetime import timedelta, datetime, UTC
from typing import TypeAlias, Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.common.enums import AuthTokenTypeEnum
from app.core.config import app_config, Configs
from app.core.logger import get_logger
from app.core.security.adapter import SecurityDependency, SecurityAdapter
from app.core.security.exceptions import ExpiredTokenError
from app.integrations.dao.refresh import RefreshTokenDAO
from app.integrations.dao.user import UserDAO
from app.integrations.database import SessionDependency
from app.models.refresh_tokens import RefreshToken
from app.schemas import command as commands
from app.schemas import result as results
from pydantic import SecretStr

from app.services.exceptions import TokenNotFoundError, UserNotFoundError


class AuthenticationService:
    def __init__(
        self,
        session: AsyncSession,
        security_adapter: SecurityAdapter,
        user_dao: UserDAO = UserDAO(),
        refresh_session_dao: RefreshTokenDAO = RefreshTokenDAO(),
        config: Configs = app_config,
    ) -> None:
        self._session = session
        self._security = security_adapter
        self._user = user_dao
        self._refresh_session = refresh_session_dao
        self._logger = get_logger("AuthenticationService")
        self._config = config.auth.jwt

    async def verify_user_by_token(
        self, cmd: commands.VerifyUserByTokenCommand
    ) -> results.UserInfo:
        """
        Verify a user by their access token.

        This method decodes and verifies the provided access token, and retrieves the corresponding user.

        Args:
            cmd (commands.VerifyUserByTokenCommand): Command object containing the access token.

        Returns:
            UserInfo: The user object corresponding to the verified token.

        Raises:
            InvalidTokenError: If the token is invalid or cannot be verified.
            UserNotFoundError: If no user is found for the given token.
        """
        user_id = await self._security.verify_token(
            cmd.token.get_secret_value(), cmd.token_type
        )
        user = await self._user.get_user_by_id(self._session, user_id)

        if not user:
            self._logger.info("User not found for token", user_id=user_id)
            raise UserNotFoundError

        return results.UserInfo.from_model(user)

    async def create_auth_session(
        self, cmd: commands.CreateAuthSessionCommand
    ) -> results.AuthTokens:
        """
        Generates authentication tokens and creates a refresh session for a user.

        Args:
            cmd (commands.CreateRefreshSession): The command containing refresh session information.

        Returns:
            results.AuthTokens: A data structure containing the access and refresh tokens.
        """
        now = datetime.now(UTC)

        access_token_raw = await self._security.generate_jwt(
            token_type=AuthTokenTypeEnum.ACCESS,
            user_id=cmd.user_id,
            created_at=now,
            expires_at=now
            + timedelta(minutes=self._config.jwt_access_lifetime_minutes),
            additional_claims={"role": cmd.role},
        )
        refresh_token_raw = await self._security.generate_jwt(
            token_type=AuthTokenTypeEnum.REFRESH,
            user_id=cmd.user_id,
            created_at=now,
            expires_at=now
            + timedelta(minutes=self._config.jwt_refresh_lifetime_minutes),
        )
        hashed_refresh_token = self._security.hash_string(refresh_token_raw)
        refresh_token = RefreshToken(
            user_id=cmd.user_id,
            token_hash=hashed_refresh_token,
            token_lifetime_minutes=self._config.jwt_refresh_lifetime_minutes,
        )
        await self._refresh_session.add_refresh_token(
            session=self._session, token=refresh_token
        )
        await self._logger.ainfo(
            "Created new auth session", user_id=cmd.user_id, role=cmd.role
        )

        return results.AuthTokens(
            access_token=SecretStr(access_token_raw),
            refresh_token=SecretStr(refresh_token_raw),
        )

    async def invalidate_refresh_token(
        self, cmd: commands.InvalidateRefreshTokenCommand
    ) -> results.UserID:
        """
        Invalidates a refresh token by removing the refresh session.

        Args:
            cmd (commands.InvalidateRefreshTokenCommand): The command containing the refresh token.

        Returns:
            results.UserID: A data structure containing the ID of the user whose refresh token was invalid

        Raises:
            TokenNotFoundError: If no refresh token is found for the provided token and user ID.
            ExpiredTokenError: If the refresh token is already revoked, indicating that all tokens for the user should be revoked.
        """
        refresh_token_raw = cmd.refresh_token.get_secret_value()
        hashed_refresh_token = self._security.hash_string(refresh_token_raw)
        refresh_token = await self._refresh_session.get_refresh_token(
            session=self._session,
            hashed_refresh_token=hashed_refresh_token,
            user_id=cmd.user_id,
        )

        if not refresh_token:
            self._logger.info("No refresh token found", user_id=cmd.user_id)
            raise TokenNotFoundError

        if refresh_token.is_revoked:
            self._logger.warning(
                "Refresh token already revoked. Revoking all rest tokens",
                user_id=cmd.user_id,
            )
            rest_tokens = await self._refresh_session.get_active_users_refresh_tokens(
                session=self._session, user_id=cmd.user_id
            )
            for token in rest_tokens:
                await self._refresh_session.invalidate_refresh_token(
                    session=self._session, token=token
                )

            raise ExpiredTokenError

        # Invalidate the refresh token
        await self._refresh_session.invalidate_refresh_token(
            session=self._session, token=refresh_token
        )
        self._logger.info(
            "Refresh token successfully revoked", user_id=refresh_token.user_id
        )

        return results.UserID(id=refresh_token.user_id)


def provide_auth_service(
    session: SessionDependency,
    security_adapter: SecurityDependency,
) -> AuthenticationService:
    return AuthenticationService(session=session, security_adapter=security_adapter)


AuthServiceDependency: TypeAlias = Annotated[
    AuthenticationService, Depends(provide_auth_service)
]
