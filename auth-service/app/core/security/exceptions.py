from app.common.exceptions import ExceptionBase
from fastapi import status


class InvalidTokenError(ExceptionBase):
    """Exception raised for invalid tokens."""

    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Invalid token."


class InvalidTokenTypeError(ExceptionBase):
    """Exception raised for invalid token type."""

    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Invalid token type."


class ExpiredTokenError(ExceptionBase):
    """Exception raised for expired tokens."""

    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Token is expired."


class TokenIsMissingError(ExceptionBase):
    """Exception raised when access_token is missing."""

    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Token is missing."
