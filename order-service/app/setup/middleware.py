import time
import base64
import json

import structlog
from asgi_correlation_id import correlation_id
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import app_config
from app.integrations.rls_context import rls_user_id, rls_db_role

import uuid

logger = structlog.get_logger(app_config.logger.api_logger_name)

# Map application-level role names (from JWT) to PostgreSQL role names.
# The service DB user must be a MEMBER of every role listed here.
_ROLE_MAP: dict[str, str] = {
    "user": "app_user",
    "admin": "app_admin",
}


class RLSContextMiddleware:
    """ASGI middleware that parses the Authorization header for JWTs and populates ContextVars for RLS."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            self._set_rls_context(scope)
        await self.app(scope, receive, send)

    @staticmethod
    def _set_rls_context(scope: Scope) -> None:
        """Parse the Authorization header and populate RLS ContextVars."""
        headers = dict(scope.get("headers", []))
        auth: bytes = headers.get(b"authorization", b"")
        auth_lower = bytes(auth).lower()
        if not auth_lower.startswith(b"bearer "):
            return

        token = auth[len(b"bearer ") :].decode()
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload: dict = json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception:
            return

        raw_uid = payload.get("sub") or payload.get("user_id")
        jwt_role = payload.get("role", "user")

        try:
            parsed_uid = uuid.UUID(str(raw_uid))
        except (TypeError, ValueError):
            return

        pg_role = _ROLE_MAP.get(jwt_role, "app_user")
        rls_user_id.set(parsed_uid)
        rls_db_role.set(pg_role)


class AccessLogMiddleware:
    """Pure ASGI middleware that logs every HTTP request/response via structlog.

    Using a pure ASGI middleware (instead of BaseHTTPMiddleware) ensures that
    ContextVars set by upstream middlewares (e.g. CorrelationIdMiddleware) are
    visible here, because BaseHTTPMiddleware runs dispatch() in a copy_context()
    snapshot that is taken *before* those vars are populated.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)  # type: ignore
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            await logger.ainfo(
                "HTTP request",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=duration_ms,
                correlation_id=correlation_id.get(),
            )
