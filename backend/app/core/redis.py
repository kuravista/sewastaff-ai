from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings


_pool: Optional[Redis] = None


async def get_redis_pool() -> Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _pool


async def get_redis() -> Redis:
    return await get_redis_pool()


async def health_check() -> bool:
    try:
        redis = await get_redis_pool()
        return bool(await redis.ping())
    except Exception:
        return False
