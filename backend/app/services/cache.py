"""Redis cache utility for dashboard and other cacheable endpoints."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config.settings import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None

DASHBOARD_CACHE_TTL = 300  # 5 minutes


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _cache_key(prefix: str, tenant_id: str, **kwargs: Any) -> str:
    parts = [prefix, tenant_id]
    for k, v in sorted(kwargs.items()):
        if v is not None:
            parts.append(f"{k}={v}")
    return ":".join(parts)


async def cache_get(key: str) -> dict | None:
    """Get a cached value. Returns None on miss or Redis error."""
    try:
        r = await get_redis()
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        logger.debug("Cache miss (error) for key=%s", key)
    return None


async def cache_set(key: str, value: Any, ttl: int = DASHBOARD_CACHE_TTL) -> None:
    """Set a cached value with TTL. Fails silently."""
    try:
        r = await get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.debug("Cache set failed for key=%s", key)


async def cache_invalidate_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern. Fails silently."""
    try:
        r = await get_redis()
        keys = []
        async for key in r.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await r.delete(*keys)
            logger.info("Cache invalidated %d keys matching %s", len(keys), pattern)
    except Exception:
        logger.debug("Cache invalidation failed for pattern=%s", pattern)


async def cache_invalidate_tenant(tenant_id: str) -> None:
    """Invalidate all dashboard cache keys for a tenant using explicit key list.

    Faster than scan_iter for known key patterns.
    """
    prefixes = ["dashboard:summary", "dashboard:trend", "dashboard:compliance-trend", "dashboard:cross-cloud"]
    try:
        r = await get_redis()
        # Build explicit keys for known patterns
        keys_to_delete = [f"{prefix}:{tenant_id}" for prefix in prefixes]
        # Trend keys have extra suffixes — use scan_iter only for those
        for prefix in ["dashboard:trend", "dashboard:compliance-trend"]:
            async for key in r.scan_iter(match=f"{prefix}:{tenant_id}:*", count=50):
                keys_to_delete.append(key)
        if keys_to_delete:
            await r.delete(*keys_to_delete)
            logger.info("Cache invalidated %d keys for tenant %s", len(keys_to_delete), tenant_id)
    except Exception:
        logger.debug("Cache invalidation failed for tenant=%s", tenant_id)
