"""Comprehensive tests for Workspace, Project, and Object-level RBAC authorization."""

import pytest
from httpx import AsyncClient

from app.core import messages
from app.core.constants import ProjectStatus, WorkspaceRole


async def _register_and_get_headers(
    client: AsyncClient, email: str, name: str
) -> dict[str, str]:
    """Helper to register and login a user, returning auth Bearer headers."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": "Password123!"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_workspace_isolation_and_ownership_rbac(
    async_client: AsyncClient,
) -> None:
    """User A's workspace cannot be accessed, updated, or deleted by User B."""
    headers_a = await _register_and_get_headers(
        async_client, "usera@taskhub.dev", "User A"
    )
    headers_b = await _register_and_get_headers(
        async_client, "userb@taskhub.dev", "User B"
    )

    # User A creates Workspace A
    res_a = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace A"},
        headers=headers_a,
    )
    assert res_a.status_code == 201
    ws_a = res_a.json()
    ws_a_id = ws_a["id"]

    # User B cannot read Workspace A -> 403
    res_b_get = await async_client.get(
        f"/api/v1/workspaces/{ws_a_id}",
        headers=headers_b,
    )
    assert res_b_get.status_code == 403
    assert res_b_get.json()["error"]["message"] == messages.NOT_WORKSPACE_MEMBER

    # User B cannot update Workspace A -> 403
    res_b_patch = await async_client.patch(
        f"/api/v1/workspaces/{ws_a_id}",
        json={"name": "Hacked Name"},
        headers=headers_b,
    )
    assert res_b_patch.status_code == 403
    assert res_b_patch.json()["error"]["message"] == messages.WORKSPACE_OWNER_REQUIRED

    # User B cannot delete Workspace A -> 403
    res_b_delete = await async_client.delete(
        f"/api/v1/workspaces/{ws_a_id}",
        headers=headers_b,
    )
    assert res_b_delete.status_code == 403
    assert res_b_delete.json()["error"]["message"] == messages.WORKSPACE_OWNER_REQUIRED

    # User A (Owner) can update Workspace A
    res_a_patch = await async_client.patch(
        f"/api/v1/workspaces/{ws_a_id}",
        json={"name": "Workspace A Renamed"},
        headers=headers_a,
    )
    assert res_a_patch.status_code == 200
    assert res_a_patch.json()["name"] == "Workspace A Renamed"


@pytest.mark.asyncio
async def test_workspace_membership_invitation_and_removal(
    async_client: AsyncClient,
) -> None:
    """Workspace OWNER can invite members; VIEWER cannot; owner cannot be removed."""
    headers_a = await _register_and_get_headers(
        async_client, "owner@taskhub.dev", "Owner User"
    )
    headers_b = await _register_and_get_headers(
        async_client, "viewer@taskhub.dev", "Viewer User"
    )
    headers_c = await _register_and_get_headers(
        async_client, "third@taskhub.dev", "Third User"
    )

    # Get User B id
    profile_b = await async_client.get("/api/v1/users/me", headers=headers_b)
    user_b_id = profile_b.json()["id"]

    # Get User C id
    profile_c = await async_client.get("/api/v1/users/me", headers=headers_c)
    user_c_id = profile_c.json()["id"]

    # Owner creates workspace
    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Team Workspace"},
        headers=headers_a,
    )
    ws_id = ws_res.json()["id"]

    # Owner invites User B as VIEWER
    invite_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": user_b_id, "role": WorkspaceRole.VIEWER},
        headers=headers_a,
    )
    assert invite_res.status_code == 201
    assert invite_res.json()["role"] == WorkspaceRole.VIEWER

    # Duplicate invite returns 409 Conflict
    dup_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": user_b_id, "role": WorkspaceRole.EDITOR},
        headers=headers_a,
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["message"] == messages.MEMBER_ALREADY_EXISTS

    # Invite nonexistent user returns 404
    nonexist_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": 99999, "role": WorkspaceRole.VIEWER},
        headers=headers_a,
    )
    assert nonexist_res.status_code == 404

    # User B is now a member and can read workspace
    get_res = await async_client.get(f"/api/v1/workspaces/{ws_id}", headers=headers_b)
    assert get_res.status_code == 200

    # User B (VIEWER) cannot invite User C -> 403
    viewer_invite = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": user_c_id, "role": WorkspaceRole.VIEWER},
        headers=headers_b,
    )
    assert viewer_invite.status_code == 403

    # Owner cannot remove themselves -> 403
    profile_a = await async_client.get("/api/v1/users/me", headers=headers_a)
    user_a_id = profile_a.json()["id"]
    remove_self_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{user_a_id}",
        headers=headers_a,
    )
    assert remove_self_res.status_code == 403
    assert (
        remove_self_res.json()["error"]["message"]
        == messages.CANNOT_REMOVE_WORKSPACE_OWNER
    )

    # User B (VIEWER) can self-leave workspace
    leave_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{user_b_id}",
        headers=headers_b,
    )
    assert leave_res.status_code == 204

    # User B is no longer member -> 403
    post_leave_get = await async_client.get(
        f"/api/v1/workspaces/{ws_id}", headers=headers_b
    )
    assert post_leave_get.status_code == 403


@pytest.mark.asyncio
async def test_project_crud_and_rbac_roles(
    async_client: AsyncClient,
) -> None:
    """Project creation/update requires OWNER or EDITOR; deletion requires OWNER."""
    headers_owner = await _register_and_get_headers(
        async_client, "proj_owner@taskhub.dev", "Proj Owner"
    )
    headers_editor = await _register_and_get_headers(
        async_client, "proj_editor@taskhub.dev", "Proj Editor"
    )
    headers_viewer = await _register_and_get_headers(
        async_client, "proj_viewer@taskhub.dev", "Proj Viewer"
    )

    profile_editor = await async_client.get("/api/v1/users/me", headers=headers_editor)
    profile_viewer = await async_client.get("/api/v1/users/me", headers=headers_viewer)
    editor_id = profile_editor.json()["id"]
    viewer_id = profile_viewer.json()["id"]

    # Owner creates workspace
    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Dev Work"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    # Add Editor and Viewer
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": editor_id, "role": WorkspaceRole.EDITOR},
        headers=headers_owner,
    )
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": viewer_id, "role": WorkspaceRole.VIEWER},
        headers=headers_owner,
    )

    # Viewer cannot create project -> 403
    v_create = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Viewer Project"},
        headers=headers_viewer,
    )
    assert v_create.status_code == 403
    assert v_create.json()["error"]["message"] == messages.PROJECT_EDITOR_REQUIRED

    # Editor can create project -> 201
    e_create = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Editor Project", "description": "Backend API"},
        headers=headers_editor,
    )
    assert e_create.status_code == 201
    proj_id = e_create.json()["id"]
    assert e_create.json()["status"] == ProjectStatus.ACTIVE

    # Viewer can read project -> 200
    v_read = await async_client.get(
        f"/api/v1/projects/{proj_id}",
        headers=headers_viewer,
    )
    assert v_read.status_code == 200
    assert v_read.json()["name"] == "Editor Project"

    # Viewer cannot update project -> 403
    v_patch = await async_client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"name": "Hacked Project"},
        headers=headers_viewer,
    )
    assert v_patch.status_code == 403

    # Editor can update and archive project -> 200
    e_patch = await async_client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"status": ProjectStatus.ARCHIVED},
        headers=headers_editor,
    )
    assert e_patch.status_code == 200
    assert e_patch.json()["status"] == ProjectStatus.ARCHIVED

    # Editor cannot delete project (OWNER required) -> 403
    e_del = await async_client.delete(
        f"/api/v1/projects/{proj_id}",
        headers=headers_editor,
    )
    assert e_del.status_code == 403
    assert e_del.json()["error"]["message"] == messages.WORKSPACE_OWNER_REQUIRED

    # Owner can delete project -> 204
    o_del = await async_client.delete(
        f"/api/v1/projects/{proj_id}",
        headers=headers_owner,
    )
    assert o_del.status_code == 204


@pytest.mark.asyncio
async def test_task_operations_rbac_in_project(
    async_client: AsyncClient,
) -> None:
    """Task CRUD requires EDITOR/OWNER; Assignee can update; VIEWER cannot delete."""
    headers_owner = await _register_and_get_headers(
        async_client, "task_owner@taskhub.dev", "Task Owner"
    )
    headers_editor = await _register_and_get_headers(
        async_client, "task_editor@taskhub.dev", "Task Editor"
    )
    headers_viewer = await _register_and_get_headers(
        async_client, "task_viewer@taskhub.dev", "Task Viewer"
    )
    headers_outsider = await _register_and_get_headers(
        async_client, "task_outsider@taskhub.dev", "Task Outsider"
    )

    profile_editor = await async_client.get("/api/v1/users/me", headers=headers_editor)
    profile_viewer = await async_client.get("/api/v1/users/me", headers=headers_viewer)
    editor_id = profile_editor.json()["id"]
    viewer_id = profile_viewer.json()["id"]

    # Setup Workspace & Project
    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Task Space"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": editor_id, "role": WorkspaceRole.EDITOR},
        headers=headers_owner,
    )
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": viewer_id, "role": WorkspaceRole.VIEWER},
        headers=headers_owner,
    )

    proj_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Sprint 1"},
        headers=headers_owner,
    )
    proj_id = proj_res.json()["id"]

    # Viewer cannot create task -> 403
    v_task_res = await async_client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Viewer Task"},
        headers=headers_viewer,
    )
    assert v_task_res.status_code == 403

    # Outsider cannot create task -> 403
    out_task_res = await async_client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Outsider Task"},
        headers=headers_outsider,
    )
    assert out_task_res.status_code == 403

    # Editor creates task assigned to Viewer -> 201
    task_res = await async_client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Implement Login", "assignee_id": viewer_id},
        headers=headers_editor,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]
    assert task_res.json()["status"] == "TODO"

    # Viewer can list tasks in project -> 200
    list_res = await async_client.get(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=headers_viewer,
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1

    # Viewer (as assignee) can update task status -> 200
    v_update_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers_viewer,
    )
    assert v_update_res.status_code == 200
    assert v_update_res.json()["status"] == "IN_PROGRESS"

    # Viewer cannot delete task -> 403
    v_del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=headers_viewer,
    )
    assert v_del_res.status_code == 403

    # Editor can delete task -> 204
    e_del_res = await async_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=headers_editor,
    )
    assert e_del_res.status_code == 204


@pytest.mark.asyncio
async def test_task_listing_workspace_isolation(
    async_client: AsyncClient,
) -> None:
    """Non-admin GET /api/v1/tasks only returns tasks from user's workspaces."""
    headers_a = await _register_and_get_headers(
        async_client, "iso_a@taskhub.dev", "User A"
    )
    headers_b = await _register_and_get_headers(
        async_client, "iso_b@taskhub.dev", "User B"
    )

    # Workspace A & Project A & Task A
    ws_a = (
        await async_client.post(
            "/api/v1/workspaces", json={"name": "Workspace A"}, headers=headers_a
        )
    ).json()
    proj_a = (
        await async_client.post(
            f"/api/v1/workspaces/{ws_a['id']}/projects",
            json={"name": "Project A"},
            headers=headers_a,
        )
    ).json()
    task_a = (
        await async_client.post(
            f"/api/v1/projects/{proj_a['id']}/tasks",
            json={"title": "Task in A"},
            headers=headers_a,
        )
    ).json()

    # Workspace B & Project B & Task B
    ws_b = (
        await async_client.post(
            "/api/v1/workspaces", json={"name": "Workspace B"}, headers=headers_b
        )
    ).json()
    proj_b = (
        await async_client.post(
            f"/api/v1/workspaces/{ws_b['id']}/projects",
            json={"name": "Project B"},
            headers=headers_b,
        )
    ).json()
    task_b = (
        await async_client.post(
            f"/api/v1/projects/{proj_b['id']}/tasks",
            json={"title": "Task in B"},
            headers=headers_b,
        )
    ).json()

    # User A listing all tasks without project_id only sees Task A
    list_a = await async_client.get("/api/v1/tasks", headers=headers_a)
    assert list_a.status_code == 200
    task_ids_a = [t["id"] for t in list_a.json()["items"]]
    assert task_a["id"] in task_ids_a
    assert task_b["id"] not in task_ids_a

    # User B listing all tasks without project_id only sees Task B
    list_b = await async_client.get("/api/v1/tasks", headers=headers_b)
    assert list_b.status_code == 200
    task_ids_b = [t["id"] for t in list_b.json()["items"]]
    assert task_b["id"] in task_ids_b
    assert task_a["id"] not in task_ids_b

    # User A cannot query tasks in Project B -> 403 Forbidden
    cross_res = await async_client.get(
        f"/api/v1/tasks?project_id={proj_b['id']}", headers=headers_a
    )
    assert cross_res.status_code == 403


@pytest.mark.asyncio
async def test_task_assignee_must_be_workspace_member(
    async_client: AsyncClient,
) -> None:
    """Assignee must be a member of the workspace (returns 422 if not)."""
    headers_owner = await _register_and_get_headers(
        async_client, "asgn_owner@taskhub.dev", "Asgn Owner"
    )
    headers_stranger = await _register_and_get_headers(
        async_client, "stranger@taskhub.dev", "Stranger"
    )

    stranger_profile = await async_client.get(
        "/api/v1/users/me", headers=headers_stranger
    )
    stranger_id = stranger_profile.json()["id"]

    ws = (
        await async_client.post(
            "/api/v1/workspaces", json={"name": "Strict Space"}, headers=headers_owner
        )
    ).json()
    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Strict Proj"},
            headers=headers_owner,
        )
    ).json()

    # Creating task with non-member assignee -> 422
    fail_create = await async_client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Invalid Assignee Task", "assignee_id": stranger_id},
        headers=headers_owner,
    )
    assert fail_create.status_code == 422
    assert (
        fail_create.json()["error"]["message"]
        == messages.ASSIGNEE_NOT_WORKSPACE_MEMBER
    )

    # Creating task with valid assignee (None) -> 201
    ok_create = await async_client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Valid Task", "assignee_id": None},
        headers=headers_owner,
    )
    assert ok_create.status_code == 201
    task_id = ok_create.json()["id"]

    # Updating task with non-member assignee -> 422
    fail_patch = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"assignee_id": stranger_id},
        headers=headers_owner,
    )
    assert fail_patch.status_code == 422
    assert (
        fail_patch.json()["error"]["message"] == messages.ASSIGNEE_NOT_WORKSPACE_MEMBER
    )


@pytest.mark.asyncio
async def test_task_assignee_viewer_can_only_update_status(
    async_client: AsyncClient,
) -> None:
    """Assignee who is VIEWER cannot modify title, description, or assignee_id."""
    headers_owner = await _register_and_get_headers(
        async_client, "status_owner@taskhub.dev", "Status Owner"
    )
    headers_viewer = await _register_and_get_headers(
        async_client, "status_viewer@taskhub.dev", "Status Viewer"
    )

    viewer_profile = await async_client.get("/api/v1/users/me", headers=headers_viewer)
    viewer_id = viewer_profile.json()["id"]

    ws = (
        await async_client.post(
            "/api/v1/workspaces", json={"name": "Role Space"}, headers=headers_owner
        )
    ).json()
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": viewer_id, "role": WorkspaceRole.VIEWER},
        headers=headers_owner,
    )

    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Role Proj"},
            headers=headers_owner,
        )
    ).json()

    task = (
        await async_client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={"title": "Viewer Assigned Task", "assignee_id": viewer_id},
            headers=headers_owner,
        )
    ).json()
    task_id = task["id"]

    # Viewer can update status -> 200
    status_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "DONE"},
        headers=headers_viewer,
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "DONE"

    # Viewer cannot update title -> 403
    title_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Hacked Title"},
        headers=headers_viewer,
    )
    assert title_res.status_code == 403
    assert title_res.json()["error"]["message"] == messages.ASSIGNEE_STATUS_ONLY

    # Viewer cannot update assignee_id -> 403
    assignee_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"assignee_id": None},
        headers=headers_viewer,
    )
    assert assignee_res.status_code == 403
    assert assignee_res.json()["error"]["message"] == messages.ASSIGNEE_STATUS_ONLY

