import asyncpg
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    statuses: dict[str, str] = {}

    # Postgres
    try:
        conn = await asyncpg.connect(settings.database_url)
        await conn.execute("SELECT 1")
        await conn.close()
        statuses["postgres"] = "ok"
    except Exception:
        statuses["postgres"] = "unavailable"

    # Kafka – lightweight probe: start a producer, fetch metadata, stop it
    try:
        from aiokafka import AIOKafkaProducer

        probe = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await probe.start()
        await probe.stop()
        statuses["kafka"] = "ok"
    except Exception:
        statuses["kafka"] = "unavailable"

    # Redis
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        await redis.aclose()
        statuses["redis"] = "ok"
    except Exception:
        statuses["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in statuses.values())
    return JSONResponse(content=statuses, status_code=200 if all_ok else 503)
