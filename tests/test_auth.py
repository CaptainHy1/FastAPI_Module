"""Tests for Authentication, JWT security, Refresh rotation, and User RBAC."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.core import messages
from app.core.config import get_settings
from app.core.constants import TokenType, UserRole


async def _register_and_login(
    client: AsyncClient,
    email: str = "member@taskhub.dev",
    full_name: str = "Member User",
    password: str = "StrongPass123!",
) -> tuple[dict[str, object], dict[str, str]]:
    """Helper to register a member user and obtain token headers + payload."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return tokens, headers


@pytest.mark.asyncio
async def test_register_ignores_client_role_and_strips_whitespace(
    async_client: AsyncClient,
) -> None:
    """Client cannot self-assign ADMIN role on register; whitespace is stripped."""
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@taskhub.dev",
            "full_name": "  Nguyen Van A  ",
            "password": "Password123!",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@taskhub.dev"
    assert data["full_name"] == "Nguyen Van A"
    assert data["role"] == UserRole.MEMBER
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(
    async_client: AsyncClient,
) -> None:
    """Trainer required case: duplicate registration returns 409 Conflict."""
    payload = {
        "email": "dup@taskhub.dev",
        "full_name": "First User",
        "password": "Password123!",
    }
    first = await async_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "DUP@taskhub.dev",
            "full_name": "Second User",
            "password": "Password123!",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["message"] == messages.EMAIL_ALREADY_EXISTS


@pytest.mark.asyncio
async def test_refresh_token_cannot_call_protected_api_401(
    async_client: AsyncClient,
) -> None:
    """Trainer required case: using refresh_token as Bearer token returns 401."""
    tokens, _ = await _register_and_login(async_client)
    resp = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"
    assert resp.json()["error"]["message"] == messages.INVALID_TOKEN_TYPE


@pytest.mark.asyncio
async def test_access_token_cannot_call_refresh_401(
    async_client: AsyncClient,
) -> None:
    """Access token rejected on refresh endpoint with 401."""
    tokens, _ = await _register_and_login(async_client)
    resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_malformed_sub_in_valid_jwt_returns_401(
    async_client: AsyncClient,
) -> None:
    """Valid-signature JWT with garbage sub claim returns 401, never 500."""
    settings = get_settings()
    now = datetime.now(UTC)
    for bad_sub in ("garbage-not-int", True, None):
        payload: dict[str, object] = {
            "type": TokenType.ACCESS.value,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=15),
        }
        if bad_sub is not None:
            payload["sub"] = bad_sub
        bad_token = jwt.encode(
            payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        resp = await async_client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_revokes_all_sessions_401(
    async_client: AsyncClient,
) -> None:
    """Reusing a revoked refresh token returns 401 and revokes all active sessions."""
    session1, _ = await _register_and_login(async_client, email="rotate@taskhub.dev")
    login2 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "rotate@taskhub.dev", "password": "StrongPass123!"},
    )
    assert login2.status_code == 200
    session2_refresh = login2.json()["refresh_token"]

    old_refresh = str(session1["refresh_token"])
    rotated = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Reuse old refresh token -> 401 AND revokes all sessions of user
    reused = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["message"] == messages.REFRESH_TOKEN_REVOKED

    # Both newly rotated token and session 2 token are now revoked
    for revoked_tok in (new_refresh, session2_refresh):
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": revoked_tok},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_password_72_byte_utf8_limit_across_endpoints(
    async_client: AsyncClient,
) -> None:
    """Passwords > 72 UTF-8 bytes (even < 72 chars) return 422 on all endpoints."""
    # 19 emojis = 19 chars, 76 UTF-8 bytes (> 72 bytes bcrypt limit)
    emoji_76_bytes = "🔐" * 19
    assert len(emoji_76_bytes) == 19
    assert len(emoji_76_bytes.encode("utf-8")) == 76

    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bytes@taskhub.dev",
            "full_name": "Byte Test",
            "password": emoji_76_bytes,
        },
    )
    assert reg_resp.status_code == 422

    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "bytes@taskhub.dev", "password": emoji_76_bytes},
    )
    assert login_resp.status_code == 422

    _, headers = await _register_and_login(async_client, email="bytes_ok@taskhub.dev")
    cp_new = await async_client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "StrongPass123!", "new_password": emoji_76_bytes},
    )
    assert cp_new.status_code == 422

    cp_old = await async_client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": emoji_76_bytes, "new_password": "NewPassword123!"},
    )
    assert cp_old.status_code == 422


@pytest.mark.asyncio
async def test_change_password_blocks_old_password_and_revokes_refresh(
    async_client: AsyncClient,
) -> None:
    """Trainer required case: old password returns 401 after change; refresh revoked."""
    tokens, headers = await _register_and_login(
        async_client, email="changepw@taskhub.dev"
    )
    cp_resp = await async_client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={
            "current_password": "StrongPass123!",
            "new_password": "NewStrongPass999!",
        },
    )
    assert cp_resp.status_code == 200

    old_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "changepw@taskhub.dev", "password": "StrongPass123!"},
    )
    assert old_login.status_code == 401

    old_refresh = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert old_refresh.status_code == 401

    new_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "changepw@taskhub.dev", "password": "NewStrongPass999!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(async_client: AsyncClient) -> None:
    """Logout atomically revokes refresh token so subsequent refresh returns 401."""
    tokens, _ = await _register_and_login(async_client, email="logout@taskhub.dev")
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_resp.status_code == 200

    refresh_after = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_after.status_code == 401


@pytest.mark.asyncio
async def test_member_cannot_modify_or_delete_other_user_403(
    async_client: AsyncClient,
) -> None:
    """Trainer required case: member updating/deleting another user returns 403."""
    _, member_headers = await _register_and_login(async_client)

    patch_resp = await async_client.patch(
        "/api/v1/users/1",
        headers=member_headers,
        json={"full_name": "Hacked Name"},
    )
    assert patch_resp.status_code == 403

    del_resp = await async_client.delete("/api/v1/users/1", headers=member_headers)
    assert del_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_user_management_and_inactive_message(
    async_client: AsyncClient,
) -> None:
    """Admin protects self and last admin; inactive user gets meaningful error."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "target@taskhub.dev",
            "full_name": "Target User",
            "password": "Password123!",
        },
    )
    target_id = reg.json()["id"]
    target_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "target@taskhub.dev", "password": "Password123!"},
    )
    target_headers = {"Authorization": f"Bearer {target_login.json()['access_token']}"}

    # Login as seeded active admin (id=1)
    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "demo@taskhub.dev", "password": "Admin1234!"},
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Admin cannot delete self or deactivate self / last active admin
    self_del = await async_client.delete("/api/v1/users/1", headers=admin_headers)
    assert self_del.status_code == 400
    assert self_del.json()["error"]["message"] == messages.CANNOT_DELETE_SELF

    self_demote = await async_client.patch(
        "/api/v1/users/1",
        headers=admin_headers,
        json={"role": "MEMBER"},
    )
    assert self_demote.status_code == 400

    # Admin deactivates target user -> target gets meaningful "inactive user" message
    deactivate = await async_client.patch(
        f"/api/v1/users/{target_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deactivate.status_code == 200

    blocked_api = await async_client.get("/api/v1/users/me", headers=target_headers)
    assert blocked_api.status_code == 403
    assert blocked_api.json()["error"]["message"] == messages.INACTIVE_USER

    blocked_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "target@taskhub.dev", "password": "Password123!"},
    )
    assert blocked_login.status_code == 403
    assert blocked_login.json()["error"]["message"] == messages.INACTIVE_USER

    # Admin can delete target user
    del_target = await async_client.delete(
        f"/api/v1/users/{target_id}", headers=admin_headers
    )
    assert del_target.status_code == 204


@pytest.mark.asyncio
async def test_user_profile_update_and_null_rejection_422(
    async_client: AsyncClient,
) -> None:
    """Profile GET/PATCH works; sending null to NOT NULL full_name returns 422."""
    _, headers = await _register_and_login(async_client, email="profile@taskhub.dev")

    me_resp = await async_client.get("/api/v1/users/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "profile@taskhub.dev"

    patch_ok = await async_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"full_name": "  Updated Name  "},
    )
    assert patch_ok.status_code == 200
    assert patch_ok.json()["full_name"] == "Updated Name"

    patch_null = await async_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"full_name": None},
    )
    assert patch_null.status_code == 422
