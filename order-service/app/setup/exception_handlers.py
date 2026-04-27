from pydantic import BaseModel, Field
from fastapi import Request
from fastapi.responses import JSONResponse

from app.common.exceptions import ExceptionBase


class ErrorDetail(BaseModel):
    """Defines the detailed structure of a single API error."""

    msg: str = Field(..., description="A human-readable message explaining the error.")
    type: str = Field(
        ..., description="A unique, machine-readable code for the error type."
    )


class ErrorResponse(BaseModel):
    """Defines the standard model for all error responses."""

    detail: list[ErrorDetail]


def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles exceptions by returning a standard JSON error response."""

    if not isinstance(exc, ExceptionBase):
        raise exc

    response_model = ErrorResponse(
        detail=[ErrorDetail(msg=exc.message, type=exc.__class__.__name__)]
    )

    return JSONResponse(
        status_code=exc.status_code, content=response_model.model_dump()
    )
