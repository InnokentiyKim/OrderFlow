from app.common.exceptions import ExceptionBase
from fastapi import status


class UserAlreadyExistsError(ExceptionBase):
    """Exception raised when trying to create a user with an email that already exists."""

    status_code = status.HTTP_409_CONFLICT
    message = "User with the given email already exists."


class InvalidCredentialsError(ExceptionBase):
    """Exception raised when credentials provided for authentication are invalid."""

    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Invalid email and (or) password."


class UserNotFoundError(ExceptionBase):
    """Exception raised when a user is not found in the system."""

    status_code = status.HTTP_404_NOT_FOUND
    message = "User with the given email not found."


class TokenNotFoundError(ExceptionBase):
    """Exception raised when refresh token is not found in the system."""

    status_code = status.HTTP_404_NOT_FOUND
    message = "Refresh token not found."
