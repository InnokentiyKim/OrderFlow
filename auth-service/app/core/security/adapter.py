import uuid
from datetime import datetime, UTC
from typing import Annotated
from fastapi import Depends

from app.common.enums import AuthTokenTypeEnum
from app.core.config import Configs, app_config
from app.core.logger import get_logger
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi.concurrency import run_in_threadpool
from jose import jwt
from app.core.security import exceptions
import hashlib
import secrets


class SecurityAdapter:
    def __init__(self, configs: Configs) -> None:
        self.config = configs.auth
        self.logger = get_logger("Security")
        self.hasher = PasswordHasher()

    async def hash_password(self, plain_password: str) -> str:
        """
        Hashes a password.

        Args:
            plain_password (str): The plain text password to be hashed.

        Returns:
            str: The hashed password.
        """

        def _hash_password(password: str) -> str:
            return self.hasher.hash(password)

        return await run_in_threadpool(_hash_password, plain_password)

    async def verify_hashed_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        """
        Verifies a password against its hashed counterpart.

        Args:
            plain_password (str): The plain text password to verify.
            hashed_password (str): The hashed password to verify against.

        Returns:
            bool: True if the password matches the hash, otherwise False.
        """

        def _verify_hashed_password(plain: str, hashed: str) -> bool:
            try:
                return self.hasher.verify(hashed, plain)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

        return await run_in_threadpool(
            _verify_hashed_password, plain_password, hashed_password
        )

    @staticmethod
    def hash_string(plain_string: str) -> str:
        """
        Hashes a string.

        Args:
            plain_string (str): The plain string to be hashed.

        Returns:
            str: The hashed string.
        """
        return hashlib.sha256(plain_string.encode()).hexdigest()

    @staticmethod
    def verify_hashed_string(plain_string: str, hashed_string: str) -> bool:
        """
        Verifies a string against its hashed counterpart.

        Args:
            plain_string (str): The plain string to verify.
            hashed_string (str): The hashed string to verify against.

        Returns:
            bool: True if the string matches the hash, otherwise False.
        """
        plain_hashed_string = hashlib.sha256(plain_string.encode()).hexdigest()
        return secrets.compare_digest(plain_hashed_string, hashed_string)

    async def generate_jwt(
        self,
        token_type: AuthTokenTypeEnum,
        user_id: str | uuid.UUID,
        created_at: datetime,
        expires_at: datetime,
        additional_claims: dict | None = None,
    ) -> str:
        """
        Generates a JWT token.

        This method encodes a JSON Web Token (JWT) using the provided payload,
        configured a secret key and algorithm.

        Args:
            token_type (AuthTokenTypeEnum): The type of token to generate.
            user_id (str): The unique identifier of the user.
            created_at (datetime): The creation timestamp for the token.
            expires_at (datetime): The expiration timestamp for the token.
            additional_claims (dict, optional): Additional claims to include in the JWT payload.

        Returns:
            str: The encoded JWT token as a string.
        """
        jwt_claims = {
            # Private Claim Names
            "sub": f"{user_id}",
            "type": token_type,
            # Registered Claim Names
            "jti": f"{uuid.uuid4()}",
            "iat": created_at,
            "exp": expires_at,
            **(additional_claims or {}),
        }

        def _generate_jwt() -> str:
            return jwt.encode(
                claims=jwt_claims,
                key=self.config.jwt.jwt_secret_key.get_secret_value(),
                algorithm=self.config.jwt.jwt_algorithm,
                headers={"kid": self.config.jwt.jwt_key_id},
            )

        return await run_in_threadpool(_generate_jwt)

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
        self, token: str, token_type: AuthTokenTypeEnum
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


SecurityDependency = Annotated[SecurityAdapter, Depends(provide_security_adapter)]
