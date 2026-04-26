from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.integrations.database import engine


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Liveness probe – returns 200 if the process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    """Readiness probe – checks PostgreSQL connectivity."""
    details: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        details["postgres"] = "ok"
    except Exception:
        details["postgres"] = "unavailable"

    all_ok = all(v == "ok" for v in details.values())
    return JSONResponse(content=details, status_code=200 if all_ok else 503)
