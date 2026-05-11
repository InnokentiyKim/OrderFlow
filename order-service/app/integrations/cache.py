import dataclasses
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from app.core.config import app_config
from app.common.enums import OrderStatusEnum
from app.integrations.redis_client import RedisClient
from app.schemas.result import GetOrderResult

logger = structlog.get_logger(__name__)

_KEY_PREFIX = "order"


def _cache_key(order_id: uuid.UUID) -> str:
    return f"{_KEY_PREFIX}:{order_id}"


def _default_serializer(obj: Any) -> Any:
    """JSON serializer for types not handled by the default encoder."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _serialize(result: GetOrderResult) -> str:
    return json.dumps(dataclasses.asdict(result), default=_default_serializer)


def _deserialize(raw: str) -> GetOrderResult:
    data = json.loads(raw)
    return GetOrderResult(
        id=uuid.UUID(data["id"]),
        user_id=uuid.UUID(data["user_id"]),
        status=OrderStatusEnum(data["status"]),
        items=data["items"],
        total_amount=Decimal(data["total_amount"]),
        currency=data["currency"],
        saga_id=uuid.UUID(data["saga_id"]) if data.get("saga_id") else None,
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


class OrderCache:
    """Cache-Aside layer for single-order reads."""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._ttl = app_config.redis.redis_cache_ttl

    async def get_order(self, order_id: uuid.UUID) -> GetOrderResult | None:
        key = _cache_key(order_id)
        raw = await self._redis.get(key)
        if raw is None:
            await logger.ainfo("Cache MISS", order_id=str(order_id))
            return None
        try:
            result = _deserialize(raw)
            await logger.ainfo("Cache HIT", order_id=str(order_id))
            return result
        except Exception as exc:
            await logger.awarning(
                "Cache deserialize error", order_id=str(order_id), error=str(exc)
            )
            return None

    async def set_order(self, result: GetOrderResult) -> None:
        key = _cache_key(result.id)
        try:
            raw = _serialize(result)
        except Exception as exc:
            await logger.awarning(
                "Cache serialize error", order_id=str(result.id), error=str(exc)
            )
            return
        await self._redis.set(key, raw, self._ttl)
        await logger.ainfo("Cache SET", order_id=str(result.id), ttl=self._ttl)

    async def invalidate(self, order_id: uuid.UUID) -> None:
        await self._redis.delete(_cache_key(order_id))
        await logger.ainfo("Cache INVALIDATED", order_id=str(order_id))
