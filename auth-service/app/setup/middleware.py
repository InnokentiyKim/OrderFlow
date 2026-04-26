import time

import structlog
from asgi_correlation_id import correlation_id
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import app_config


logger = structlog.get_logger(app_config.logger.api_logger_name)


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
