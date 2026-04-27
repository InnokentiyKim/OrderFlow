from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.integrations.database import engine
from app.core.config import app_config

from aiokafka import AIOKafkaProducer

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Liveness probe – returns 200 if the process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    """Readiness probe – checks PostgreSQL and Kafka connectivity."""
    details: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        details["postgres"] = "ok"
    except Exception:
        details["postgres"] = "unavailable"

    producer: AIOKafkaProducer | None = None
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=app_config.broker.kafka_bootstrap_servers,
            request_timeout_ms=5_000,
            metadata_max_age_ms=5_000,
        )
        await producer.start()
        details["kafka"] = "ok"
    except Exception:
        details["kafka"] = "unavailable"
    finally:
        if producer is not None:
            try:
                await producer.stop()
            except Exception:
                pass

    all_ok = all(v == "ok" for v in details.values())
    return JSONResponse(content=details, status_code=200 if all_ok else 503)
