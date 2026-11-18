"""Async Redis caching manager with fail-open degradation and key invalidation."""

import hashlib
import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.constants import (
    DEFAULT_CACHE_TTL_SECONDS,
    PROJECT_TASKS_CACHE_PREFIX,
    PROJECT_TASKS_CACHE_RESOURCE,
)

logger = logging.getLogger("taskhub.cache")


class CacheManager:
    """Async Redis cache abstraction for TaskHub API.

    Fails open on Redis connectivity errors so database-backed endpoints remain
    available even when the cache tier is temporarily unreachable.
    """

    def __init__(
        self,
        client: Redis | None = None,
        default_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._default_ttl = default_ttl

    @property
    def client(self) -> Redis | None:
        """Return the underlying async Redis client if connected."""
        return self._client

    def set_client(self, client: Redis | None, ttl: int | None = None) -> None:
        """Attach or replace the Redis client (used by lifespan and tests)."""
        self._client = client
        if ttl is not None:
            self._default_ttl = ttl

    async def connect(self, redis_url: str, ttl: int | None = None) -> None:
        """Initialize async Redis connection pool and verify connectivity."""
        if ttl is not None:
            self._default_ttl = ttl
        client: Redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        try:
            await client.ping()
            self._client = client
            logger.info("Connected to Redis cache at %s", redis_url)
        except (RedisError, OSError) as exc:
            logger.warning(
                "Redis unavailable at %s (%s). Continuing with cache disabled.",
                redis_url,
                exc,
            )
            await client.aclose()
            self._client = None

    async def close(self) -> None:
        """Gracefully close Redis connections on application shutdown."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except (RedisError, OSError) as exc:
                logger.warning("Error closing Redis connection: %s", exc)
            finally:
                self._client = None

    @staticmethod
    def build_project_tasks_key(
        project_id: int,
        page: int,
        page_size: int,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: int | None = None,
        search: str | None = None,
    ) -> str:
        """Build a deterministic Redis key for a project's filtered task listing."""
        query_payload = json.dumps(
            {
                "page": page,
                "page_size": page_size,
                "status": status,
                "priority": priority,
                "assignee_id": assignee_id,
                "search": search,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(query_payload.encode("utf-8")).hexdigest()[:16]
        return (
            f"{PROJECT_TASKS_CACHE_PREFIX}:{project_id}:"
            f"{PROJECT_TASKS_CACHE_RESOURCE}:{digest}"
        )

    @staticmethod
    def build_project_tasks_pattern(project_id: int) -> str:
        """Build the scan pattern matching all cached pages for a project."""
        return (
            f"{PROJECT_TASKS_CACHE_PREFIX}:{project_id}:"
            f"{PROJECT_TASKS_CACHE_RESOURCE}:*"
        )

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve and deserialize a JSON object from Redis, failing open on errors."""
        if self._client is None:
            return None
        try:
            raw = await self._client.get(key)
            if raw is None:
                return None
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return None
        except (RedisError, OSError, json.JSONDecodeError) as exc:
            logger.warning("Redis GET failed for key '%s': %s", key, exc)
            return None

    async def set_json(
        self, key: str, value: dict[str, Any], ttl: int | None = None
    ) -> None:
        """Serialize and store a JSON object in Redis with TTL."""
        if self._client is None:
            return
        try:
            payload = json.dumps(value, default=str)
            await self._client.set(key, payload, ex=ttl or self._default_ttl)
        except (RedisError, OSError, TypeError) as exc:
            logger.warning("Redis SET failed for key '%s': %s", key, exc)

    async def invalidate_project_tasks(self, project_id: int) -> int:
        """Invalidate all cached task listing entries for a project via SCAN."""
        if self._client is None:
            return 0
        pattern = self.build_project_tasks_pattern(project_id)
        try:
            keys: list[str] = [
                key async for key in self._client.scan_iter(match=pattern)
            ]
            if not keys:
                return 0
            deleted = await self._client.delete(*keys)
            logger.debug(
                "Invalidated %d cached task key(s) for project %d",
                deleted,
                project_id,
            )
            return int(deleted)
        except (RedisError, OSError) as exc:
            logger.warning(
                "Redis invalidation failed for project %d: %s", project_id, exc
            )
            return 0


cache_manager = CacheManager(default_ttl=get_settings().CACHE_TTL_SECONDS)


def get_cache_manager() -> CacheManager:
    """FastAPI dependency returning the shared CacheManager instance."""
    return cache_manager
