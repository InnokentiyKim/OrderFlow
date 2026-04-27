import uuid

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from typing import AsyncGenerator

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.routers.common import http_router_v1
from app.api.routers.health import router as health_router
from app.core.config import app_config
from app.core.logger import setup_logging
from app.setup.exception_handlers import general_exception_handler
from app.setup.middleware import AccessLogMiddleware, RLSContextMiddleware
from app.integrations.database import engine
from app.integrations.kafka import KafkaProducerClient
from app.common.exceptions import ExceptionBase
from app.setup.rls_setup import apply_rls_setup


logger = structlog.get_logger(app_config.logger.app_logger_name)


def _is_valid_uuid(value: str) -> bool:
    """Validator that accepts UUIDs with or without hyphens."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    await logger.ainfo(
        "Application starting up",
        service=app_config.general.service_name,
        version=app_config.general.service_version,
        environment=app_config.general.environment,
    )

    producer = KafkaProducerClient()
    await producer.start()
    app.state.kafka_producer = producer

    # Bootstrap RLS roles + policies once per startup (idempotent).
    # Runs AFTER Alembic migrations — tables must exist before we set policies.
    await apply_rls_setup(engine)

    yield

    await producer.stop()
    await engine.dispose()
    await logger.ainfo(
        "Application shutting down",
        service=app_config.general.service_name,
    )


def create_fastapi_app() -> FastAPI:
    """Creates and configures the FastAPI application."""
    setup_logging(app_config)

    app = FastAPI(
        title="Order Service API",
        version="1.0.0",
        description="Order management service",
        lifespan=lifespan,
    )

    app.add_exception_handler(ExceptionBase, general_exception_handler)
    app.add_middleware(AccessLogMiddleware)  # type: ignore[arg-type]
    app.add_middleware(RLSContextMiddleware)  # type: ignore[arg-type]  # sets RLS ContextVars from JWT
    app.add_middleware(CorrelationIdMiddleware, validator=_is_valid_uuid)  # type: ignore[arg-type]

    app.include_router(health_router)
    app.include_router(http_router_v1)

    return app
