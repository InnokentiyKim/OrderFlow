from fastapi import status


class ExceptionBase(Exception):
    """Base class for all exceptions in the application."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An internal server error occurred"

    def __init__(self, message: str = "", status_code: int = 0):
        self.message = message or self.message
        self.status_code = status_code or self.status_code

        super().__init__(self.message)


class ItemAlreadyExistsError(ExceptionBase):
    """Item already exists."""

    status_code: int = status.HTTP_409_CONFLICT
    message: str = "Item already exists."


class ItemNotFoundError(ExceptionBase):
    """Item not found."""

    status_code: int = status.HTTP_404_NOT_FOUND
    message: str = "Item not found."


class Unauthorized(ExceptionBase):  # noqa: N818
    """Exception raised when a user is unauthorized."""

    status_code: int = status.HTTP_401_UNAUTHORIZED
    message: str = "Unauthorized"


class Forbidden(ExceptionBase):
    """Exception raised when a user is forbidden from accessing a resource."""

    status_code: int = status.HTTP_403_FORBIDDEN
    message: str = "Forbidden"


class DatabaseError(ExceptionBase):
    """Database error."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Database error."
