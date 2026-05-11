import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import app_config

logger = structlog.get_logger(__name__)

# Exceptions that can escape redis-py when the socket layer misbehaves
# (e.g. asyncio.TimeoutError before redis-py wraps it, OSError on broken pipe).
_REDIS_EXCEPTIONS = (RedisError, OSError, TimeoutError)


class RedisClient:
    """Thin wrapper around redis.asyncio.Redis with graceful error handling.

    All public methods are *guaranteed* never to raise – on any Redis failure
    they log a warning and return a safe default so the application continues
    to serve requests directly from the database.
    """

    def __init__(self) -> None:
        cfg = app_config.redis
        _raw_password = (
            cfg.redis_password.get_secret_value() if cfg.redis_password else ""
        )
        password = _raw_password or None
        self._redis: Redis = Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            password=password,
            decode_responses=True,
            socket_timeout=cfg.redis_socket_timeout,
            socket_connect_timeout=cfg.redis_socket_connect_timeout,
        )

    async def start(self) -> None:
        """Ping Redis to verify connectivity; logs a warning if unavailable."""
        cfg = app_config.redis
        try:
            await self._redis.ping()
            await logger.ainfo(
                "Redis client initialised and reachable",
                host=cfg.redis_host,
                port=cfg.redis_port,
            )
        except _REDIS_EXCEPTIONS as exc:
            await logger.awarning(
                "Redis is unavailable at startup – cache disabled, app will use DB only",
                host=cfg.redis_host,
                port=cfg.redis_port,
                error=str(exc),
            )

    async def stop(self) -> None:
        try:
            await self._redis.aclose()
            await logger.ainfo("Redis client closed")
        except _REDIS_EXCEPTIONS as exc:
            await logger.awarning("Redis close error (ignored)", error=str(exc))

    async def get(self, key: str) -> str | None:
        """Return cached value or None; never raises."""
        try:
            return await self._redis.get(key)
        except _REDIS_EXCEPTIONS as exc:
            await logger.awarning("Redis GET failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Store value with TTL; never raises."""
        try:
            await self._redis.set(key, value, ex=ttl)
        except _REDIS_EXCEPTIONS as exc:
            await logger.awarning("Redis SET failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        """Delete a key; never raises."""
        try:
            await self._redis.delete(key)
        except _REDIS_EXCEPTIONS as exc:
            await logger.awarning("Redis DELETE failed", key=key, error=str(exc))
