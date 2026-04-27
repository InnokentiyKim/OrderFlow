from app.setup.fastapi_app import create_fastapi_app
from app.core.config import app_config
import asyncio
import uvicorn


async def _start_app(port: int) -> None:
    """Start the FastAPI application."""
    fastapi_app = create_fastapi_app()

    uvicorn_config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_config=None,
        access_log=False,
    )

    server = uvicorn.Server(uvicorn_config)
    await server.serve()


def start_app(port: int = 8000) -> None:
    """Start the FastAPI application on the specified port."""
    asyncio.run(_start_app(port=port))


if __name__ == "__main__":
    start_app(app_config.general.app_port)
