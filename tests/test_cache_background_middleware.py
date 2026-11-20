"""Tests for Day 6: Redis caching, versioned invalidation, and middleware."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from redis.exceptions import RedisError

from app.core.cache import cache_manager
from app.core.constants import (
    HEADER_PROCESS_TIME,
    HEADER_REQUEST_ID,
    WorkspaceRole,
)
from app.services import task as task_service_module


class FakeRedis:
    """In-memory async Redis stub with versioned keys for deterministic tests."""

    def __init__(self, fail_on_ops: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.get_calls: int = 0
        self.set_calls: int = 0
        self.incr_calls: int = 0
        self.delete_calls: int = 0
        self.fail_on_ops = fail_on_ops

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        if self.fail_on_ops:
            raise RedisError("Redis unavailable")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.set_calls += 1
        if self.fail_on_ops:
            raise RedisError("Redis unavailable")
        self.store[key] = value
        return True

    async def incr(self, key: str) -> int:
        self.incr_calls += 1
        if self.fail_on_ops:
            raise RedisError("Redis unavailable")
        current = int(self.store.get(key, 0)) + 1
        self.store[key] = str(current)
        return current

    async def expire(self, key: str, time: int) -> bool:
        if self.fail_on_ops:
            raise RedisError("Redis unavailable")
        return True

    async def delete(self, *keys: str) -> int:
        self.delete_calls += 1
        if self.fail_on_ops:
            raise RedisError("Redis unavailable")
        removed = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                removed += 1
        return removed

    async def aclose(self) -> None:
        self.store.clear()


@pytest.fixture
def fake_redis() -> Any:
    """Attach FakeRedis to shared cache_manager and clean up after test."""
    stub = FakeRedis()
    cache_manager.set_client(stub, ttl=60)  # type: ignore[arg-type]
    yield stub
    cache_manager.set_client(None)


async def _register_and_login(
    client: AsyncClient, email: str, name: str
) -> tuple[int, dict[str, str]]:
    """Helper to register, login, and return (user_id, auth_headers)."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": "Password123!"},
    )
    assert reg.status_code == 201
    user_id = int(reg.json()["id"])
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return user_id, headers


@pytest.mark.asyncio
async def test_project_tasks_redis_cache_hit_miss_and_invalidation(
    async_client: AsyncClient,
    admin_auth_headers: dict[str, str],
    fake_redis: FakeRedis,
) -> None:
    """Verify cache MISS/HIT and O(1) version invalidation on mutations."""
    # Seed initial task
    create_res = await async_client.post(
        "/api/v1/projects/1/tasks",
        json={"title": "Cached Task 1"},
        headers=admin_auth_headers,
    )
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # First GET -> Cache MISS -> stored in Redis under version 1
    res1 = await async_client.get(
        "/api/v1/projects/1/tasks", headers=admin_auth_headers
    )
    assert res1.status_code == 200
    assert res1.json()["total"] == 1
    assert fake_redis.get_calls >= 1
    assert fake_redis.set_calls == 1

    # Second GET -> Cache HIT -> no additional SET
    previous_sets = fake_redis.set_calls
    res2 = await async_client.get(
        "/api/v1/projects/1/tasks", headers=admin_auth_headers
    )
    assert res2.status_code == 200
    assert res2.json()["total"] == 1
    assert fake_redis.set_calls == previous_sets

    # Unauthorized non-member must still receive 403 even when cache is warm
    _, outsider_headers = await _register_and_login(
        async_client, "cache_outsider@taskhub.dev", "Outsider"
    )
    res_forbidden = await async_client.get(
        "/api/v1/projects/1/tasks", headers=outsider_headers
    )
    assert res_forbidden.status_code == 403

    # Creating a new task increments project version (O(1) invalidation)
    v_before = int(fake_redis.store.get("project:1:tasks:ver", 0))
    create_res2 = await async_client.post(
        "/api/v1/projects/1/tasks",
        json={"title": "Cached Task 2"},
        headers=admin_auth_headers,
    )
    assert create_res2.status_code == 201
    assert int(fake_redis.store.get("project:1:tasks:ver", 0)) > v_before

    # Next GET misses the old version, fetches from DB, returns total=2, caches under v2
    res3 = await async_client.get(
        "/api/v1/projects/1/tasks", headers=admin_auth_headers
    )
    assert res3.status_code == 200
    assert res3.json()["total"] == 2

    # Updating task increments version again
    patch_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Updated Cached Task"},
        headers=admin_auth_headers,
    )
    assert patch_res.status_code == 200
    assert fake_redis.store.get("project:1:tasks:ver") == "3"

    # Repopulate then attach label -> increments version
    await async_client.get("/api/v1/projects/1/tasks", headers=admin_auth_headers)
    lbl = (
        await async_client.post(
            "/api/v1/projects/1/labels",
            json={"name": "cache-tag", "color": "#11AA22"},
            headers=admin_auth_headers,
        )
    ).json()
    attach = await async_client.post(
        f"/api/v1/tasks/{task_id}/labels/{lbl['id']}",
        headers=admin_auth_headers,
    )
    assert attach.status_code == 200
    assert fake_redis.store.get("project:1:tasks:ver") == "4"

    # Repopulate then delete task -> increments version
    await async_client.get("/api/v1/projects/1/tasks", headers=admin_auth_headers)
    del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}", headers=admin_auth_headers
    )
    assert del_res.status_code == 204
    assert fake_redis.store.get("project:1:tasks:ver") == "5"


@pytest.mark.asyncio
async def test_redis_fail_open_when_unavailable(
    async_client: AsyncClient,
    admin_auth_headers: dict[str, str],
) -> None:
    """API continues serving requests from DB if Redis throws connectivity errors."""
    broken_redis = FakeRedis(fail_on_ops=True)
    cache_manager.set_client(broken_redis, ttl=60)  # type: ignore[arg-type]
    try:
        res = await async_client.get(
            "/api/v1/projects/1/tasks", headers=admin_auth_headers
        )
        assert res.status_code == 200
        assert res.json()["items"] == []
    finally:
        cache_manager.set_client(None)


@pytest.mark.asyncio
async def test_cache_payload_schema_mismatch_fallback(
    async_client: AsyncClient,
    admin_auth_headers: dict[str, str],
    fake_redis: FakeRedis,
) -> None:
    """Malformed cache payloads fail open as cache miss instead of 500."""
    ver = await cache_manager.get_project_version(1)
    bad_key = cache_manager.build_project_tasks_key(
        project_id=1,
        version=ver,
        page=1,
        page_size=10,
    )
    # Store corrupted schema missing required 'items', 'total', etc.
    fake_redis.store[bad_key] = '{"invalid_structure": 12345}'

    res = await async_client.get("/api/v1/projects/1/tasks", headers=admin_auth_headers)
    assert res.status_code == 200
    assert "items" in res.json()
    assert "total" in res.json()


@pytest.mark.asyncio
async def test_tasks_list_workspace_isolation_for_outsider(
    async_client: AsyncClient,
) -> None:
    """Outsiders calling GET /api/v1/tasks without project_id see 0 tasks."""
    _, owner_headers = await _register_and_login(
        async_client, "ws_owner_isolation@taskhub.dev", "Owner"
    )
    _, outsider_headers = await _register_and_login(
        async_client, "ws_outsider_isolation@taskhub.dev", "Outsider"
    )

    ws = (
        await async_client.post(
            "/api/v1/workspaces",
            json={"name": "Secret WS"},
            headers=owner_headers,
        )
    ).json()

    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Secret Project"},
            headers=owner_headers,
        )
    ).json()

    await async_client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Top Secret Task"},
        headers=owner_headers,
    )

    # Outsider lists all tasks without project_id filter
    outsider_list = await async_client.get("/api/v1/tasks", headers=outsider_headers)
    assert outsider_list.status_code == 200
    assert outsider_list.json()["total"] == 0
    assert outsider_list.json()["items"] == []


@pytest.mark.asyncio
async def test_background_task_notification_on_task_assignment(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Background task notifies assignee with non-PII primitives only."""
    mock_notify = MagicMock()
    monkeypatch.setattr(
        task_service_module, "send_task_assigned_notification", mock_notify
    )

    owner_id, owner_headers = await _register_and_login(
        async_client, "bg_owner@taskhub.dev", "Owner"
    )
    member_id, _ = await _register_and_login(
        async_client, "bg_member@taskhub.dev", "Assignee Member"
    )

    ws = (
        await async_client.post(
            "/api/v1/workspaces",
            json={"name": "Notify WS"},
            headers=owner_headers,
        )
    ).json()
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": member_id, "role": WorkspaceRole.EDITOR},
        headers=owner_headers,
    )
    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Notify Project"},
            headers=owner_headers,
        )
    ).json()

    # 1. Creating task WITH assignee_id triggers notification once with primitive IDs
    res_create = await async_client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Assigned on Create", "assignee_id": member_id},
        headers=owner_headers,
    )
    assert res_create.status_code == 201
    task_id = res_create.json()["id"]
    assert mock_notify.call_count == 1
    assert mock_notify.call_args.kwargs["recipient_id"] == member_id
    assert mock_notify.call_args.kwargs["task_id"] == task_id
    assert mock_notify.call_args.kwargs["project_id"] == proj["id"]
    assert mock_notify.call_args.kwargs["assigned_by_id"] == owner_id

    # 2. Updating title only (assignee unchanged) does NOT re-trigger notification
    res_patch_title = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Renamed Task"},
        headers=owner_headers,
    )
    assert res_patch_title.status_code == 200
    assert mock_notify.call_count == 1

    # 3. Creating unassigned task then assigning via PATCH triggers notification
    res_unassigned = await async_client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Unassigned Initially"},
        headers=owner_headers,
    )
    assert res_unassigned.status_code == 201
    assert mock_notify.call_count == 1

    task_id2 = res_unassigned.json()["id"]
    res_assign = await async_client.patch(
        f"/api/v1/tasks/{task_id2}",
        json={"assignee_id": member_id},
        headers=owner_headers,
    )
    assert res_assign.status_code == 200
    assert mock_notify.call_count == 2
    assert mock_notify.call_args.kwargs["task_id"] == task_id2
    assert mock_notify.call_args.kwargs["recipient_id"] == member_id


@pytest.mark.asyncio
async def test_request_logging_middleware_headers(async_client: AsyncClient) -> None:
    """Middleware injects X-Request-ID/X-Process-Time and preserves valid ID."""
    res1 = await async_client.get("/api/v1/health")
    assert res1.status_code == 200
    assert HEADER_REQUEST_ID in res1.headers
    assert len(res1.headers[HEADER_REQUEST_ID]) >= 32
    assert HEADER_PROCESS_TIME in res1.headers
    assert res1.headers[HEADER_PROCESS_TIME].endswith("ms")

    custom_id = "trace-day6-12345"
    res2 = await async_client.get(
        "/api/v1/health", headers={HEADER_REQUEST_ID: custom_id}
    )
    assert res2.status_code == 200
    assert res2.headers[HEADER_REQUEST_ID] == custom_id


@pytest.mark.asyncio
async def test_request_logging_crlf_and_invalid_request_id(
    async_client: AsyncClient,
) -> None:
    """Middleware rejects CRLF and overlong IDs, replacing with fresh UUID."""
    # Attempt CRLF injection
    crlf_id = "malicious-id\r\nInjected-Header: evil"
    res_crlf = await async_client.get(
        "/api/v1/health", headers={HEADER_REQUEST_ID: crlf_id}
    )
    assert res_crlf.status_code == 200
    # Must NOT return the injected CRLF header value
    assert res_crlf.headers[HEADER_REQUEST_ID] != crlf_id
    assert len(res_crlf.headers[HEADER_REQUEST_ID]) >= 32

    # Overlong ID > 64 chars
    long_id = "a" * 100
    res_long = await async_client.get(
        "/api/v1/health", headers={HEADER_REQUEST_ID: long_id}
    )
    assert res_long.status_code == 200
    assert res_long.headers[HEADER_REQUEST_ID] != long_id
    assert len(res_long.headers[HEADER_REQUEST_ID]) >= 32
