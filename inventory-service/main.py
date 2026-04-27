import uvicorn

from app.config import settings
from app.fastapi_app import app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run(
        "app.fastapi_app:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )

