"""Async Redis caching manager with versioned keys and fail-open design."""

import hashlib
import json
import logging
import time
import urllib.parse
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.constants import (
    CACHE_KEY_DIGEST_LENGTH,
    CACHE_SCHEMA_VERSION,
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    DEFAULT_CACHE_TTL_SECONDS,
    REDIS_CONNECT_TIMEOUT,
    REDIS_SOCKET_TIMEOUT,
)

logger = logging.getLogger("taskhub.cache")


def mask_redis_url(url: str) -> str:
    """Mask credentials in Redis connection string to prevent log leakage."""
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.password:
            user = parsed.username or ""
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{user}:***@{host}{port}"
            return urllib.parse.urlunsplit(
                (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
            )
        return url
    except Exception:
        return "redis://***"


class CacheManager:
    """Async Redis cache abstraction with versioned invalidation and circuit breaker.

    Fails open on Redis errors so database-backed operations remain operational
    even when the Redis caching tier is down or recovering.
    """

    def __init__(
        self,
        client: Redis | None = None,
        default_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        circuit_cooldown: float = CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    ) -> None:
        self._client = client
        self._default_ttl = default_ttl
        self._circuit_cooldown = circuit_cooldown
        self._circuit_open_until: float | None = None

    @property
    def client(self) -> Redis | None:
        """Return the underlying async Redis client."""
        return self._client

    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open (Redis cooling down after error)."""
        if self._circuit_open_until is None:
            return False
        if time.monotonic() < self._circuit_open_until:
            return True
        self._circuit_open_until = None
        return False

    def record_failure(self, exc: Exception) -> None:
        """Trip circuit breaker for cooldown period on Redis connectivity errors."""
        self._circuit_open_until = time.monotonic() + self._circuit_cooldown
        logger.warning(
            "Redis failure (%s). Tripping circuit breaker for %.1fs.",
            exc,
            self._circuit_cooldown,
        )

    def record_success(self) -> None:
        """Reset circuit breaker on successful operation."""
        self._circuit_open_until = None

    def set_client(self, client: Redis | None, ttl: int | None = None) -> None:
        """Attach or replace the Redis client (used by lifespan and test fixtures)."""
        self._client = client
        self._circuit_open_until = None
        if ttl is not None:
            self._default_ttl = ttl

    async def connect(
        self,
        redis_url: str,
        ttl: int | None = None,
        socket_timeout: float = REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout: float = REDIS_CONNECT_TIMEOUT,
    ) -> None:
        """Initialize async Redis client and verify connectivity."""
        if ttl is not None:
            self._default_ttl = ttl

        masked_url = mask_redis_url(redis_url)
        client: Redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
        )
        self._client = client
        try:
            await client.ping()
            self.record_success()
            logger.info("Connected to Redis cache at %s", masked_url)
        except (RedisError, OSError) as exc:
            self.record_failure(exc)
            logger.warning(
                "Redis unavailable at %s (%s). Retaining client for reconnect.",
                masked_url,
                exc,
            )

    async def close(self) -> None:
        """Gracefully close Redis connections on application shutdown."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except (RedisError, OSError) as exc:
                logger.warning("Error closing Redis connection: %s", exc)
            finally:
                self._client = None
                self._circuit_open_until = None

    async def get_project_version(self, project_id: int) -> int:
        """Retrieve current cache version for a project, defaulting to 1."""
        if self._client is None or self.is_circuit_open():
            return 1
        try:
            ver = await self._client.get(f"project:{project_id}:tasks:ver")
            self.record_success()
            return int(ver) if ver else 1
        except (RedisError, OSError) as exc:
            self.record_failure(exc)
            return 1

    def build_project_tasks_key(
        self,
        project_id: int,
        version: int,
        page: int,
        page_size: int,
        status: list[str] | str | None = None,
        priority: list[str] | str | None = None,
        assignee_id: int | None = None,
        search: str | None = None,
    ) -> str:
        """Build deterministic versioned cache key with schema versioning."""
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
        digest = hashlib.sha256(query_payload.encode("utf-8")).hexdigest()[
            :CACHE_KEY_DIGEST_LENGTH
        ]
        return f"project:{project_id}:tasks:s{CACHE_SCHEMA_VERSION}:v{version}:{digest}"

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve and deserialize a JSON object from Redis, failing open on errors."""
        if self._client is None or self.is_circuit_open():
            return None
        try:
            raw = await self._client.get(key)
            if raw is None:
                return None
            parsed = json.loads(raw)
            self.record_success()
            if isinstance(parsed, dict):
                return parsed
            return None
        except (RedisError, OSError) as exc:
            self.record_failure(exc)
            return None
        except json.JSONDecodeError as exc:
            logger.warning("Corrupted JSON in cache for key '%s': %s", key, exc)
            return None

    async def set_json(
        self, key: str, value: dict[str, Any], ttl: int | None = None
    ) -> None:
        """Serialize and store a JSON object in Redis with TTL."""
        if self._client is None or self.is_circuit_open():
            return
        try:
            payload = json.dumps(value, default=str)
            await self._client.set(key, payload, ex=ttl or self._default_ttl)
            self.record_success()
        except (RedisError, OSError) as exc:
            self.record_failure(exc)
        except TypeError as exc:
            logger.warning("Failed to serialize cache value for key '%s': %s", key, exc)

    async def invalidate_project_tasks(self, project_id: int) -> int:
        """Invalidate cached task listings via atomic project version bump (O(1))."""
        if self._client is None or self.is_circuit_open():
            return 0
        ver_key = f"project:{project_id}:tasks:ver"
        try:
            new_ver = await self._client.incr(ver_key)
            await self._client.expire(ver_key, self._default_ttl * 10)
            self.record_success()
            logger.debug(
                "Incremented cache version for project %d to %d",
                project_id,
                new_ver,
            )
            return int(new_ver)
        except (RedisError, OSError) as exc:
            self.record_failure(exc)
            return 0


cache_manager = CacheManager(default_ttl=get_settings().CACHE_TTL_SECONDS)


def get_cache_manager() -> CacheManager:
    """FastAPI dependency returning the shared CacheManager instance."""
    return cache_manager
