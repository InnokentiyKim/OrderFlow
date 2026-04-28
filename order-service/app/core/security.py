import uuid
from datetime import datetime, UTC
from typing import Annotated, TypeAlias

from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

from app.common.enums import AuthTokenTypeEnum
from app.core import exceptions
from app.core.config import Configs, app_config
from app.core.logger import get_logger
from app.schemas.result import CurrentUser

_bearer = HTTPBearer(auto_error=True)


class SecurityAdapter:
    def __init__(self, configs: Configs) -> None:
        self.config = configs.auth
        self.logger = get_logger("Security")

    async def decode_jwt(self, token: str) -> dict[str, str]:
        """
        Decodes a JWT token.

        This method verifies and decodes a JSON Web Token (JWT) using the configured
        secret key and algorithm. If the token format is invalid, an exception is raised.

        Args:
            token (str): The JWT token to decode.

        Returns:
            dict: The decoded payload of the JWT token.

        Raises:
            InvalidTokenError: If the token is invalid or cannot be decoded.
        """

        def _decode_jwt() -> dict[str, str]:
            try:
                return jwt.decode(
                    token=token,
                    key=self.config.jwt.jwt_secret_key.get_secret_value(),
                    algorithms=[self.config.jwt.jwt_algorithm],
                )
            except (jwt.JWTError, jwt.ExpiredSignatureError) as err:
                self.logger.warning("Invalid JWT token attempt", error=f"{err}")
                raise exceptions.InvalidTokenError from None

        return await run_in_threadpool(_decode_jwt)

    async def verify_token(
        self, token: str, token_type: AuthTokenTypeEnum = AuthTokenTypeEnum.ACCESS
    ) -> uuid.UUID:
        """
        Verify a JWT token.

        This method decodes the token and checks its expiration. If the token is valid, it returns the user ID.

        Args:
            token (str): The JWT token to verify.
            token_type (AuthTokenTypeEnum): The type of the access_token (e.g., access, refresh).

        Returns:
            UUID: The user ID extracted from the token if valid.

        Raises:
            InvalidTokenTypeError: If the token type does not match the expected type.
            InvalidTokenError: If the token is invalid or missing required claims.
            ExpiredTokenError: If the token has expired.
        """
        payload = await self.decode_jwt(token)

        jwt_type = payload.get("type")
        expire = payload.get("exp")
        user_id = uuid.UUID(payload.get("sub"))

        if token_type != jwt_type:
            self.logger.info("Invalid token type attempt")
            raise exceptions.InvalidTokenTypeError

        if not expire or not user_id:
            self.logger.info("Invalid token attempt")
            raise exceptions.InvalidTokenError

        if int(expire) < int(datetime.now(UTC).timestamp()):
            self.logger.info("Expired token attempt")
            raise exceptions.ExpiredTokenError

        return user_id


def provide_security_adapter() -> SecurityAdapter:
    """
    Dependency provider for SecurityAdapter.

    Returns:
        SecurityAdapter: An instance of the SecurityAdapter class.
    """
    return SecurityAdapter(configs=app_config)


async def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    security: SecurityAdapter = Depends(provide_security_adapter),
) -> CurrentUser:
    """Get the current user from the access token."""
    token = credentials.credentials
    # verify_token checks signature, expiry and token_type
    user_id = await security.verify_token(token, AuthTokenTypeEnum.ACCESS)
    # decode again to get role (payload already verified above)
    payload = await security.decode_jwt(token)
    role = payload.get("role", "user")
    return CurrentUser(user_id=user_id, role=role)


CurrentUserDep: TypeAlias = Annotated[CurrentUser, Depends(_get_current_user)]
