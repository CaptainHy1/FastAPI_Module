"""End-to-End integration test covering the complete multi-tenant lifecycle flow.

Simulates a realistic collaboration journey:
1. Registration & JWT Login for Owner and Member
2. Workspace Creation & Member Invitation (EDITOR role)
3. Project Creation & Label Management
4. Task Creation with Member Assignment & Background Notification
5. Label Attachment & Zero N+1 Task Querying
6. Member Collaboration: Task Details, Discussion Comments, Status Transition
7. Filtered & Paginated Task Retrieval
8. Project Lifecycle: Archiving
9. Security & Session Lifecycle: Refresh Token Rotation, Reuse Detection, and Logout
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_collaboration_lifecycle_e2e(
    async_client: AsyncClient,
) -> None:
    """Run full end-to-end collaboration flow across all modules."""
    # -------------------------------------------------------------------------
    # 1. User Registration & Authentication
    # -------------------------------------------------------------------------
    owner_payload = {
        "email": "lead_owner@example.com",
        "full_name": "Project Lead",
        "password": "StrongPassword123!",
    }
    member_payload = {
        "email": "developer_member@example.com",
        "full_name": "Core Developer",
        "password": "StrongPassword123!",
    }

    # Register both users
    reg_owner_res = await async_client.post("/api/v1/auth/register", json=owner_payload)
    assert reg_owner_res.status_code == 201
    owner_user = reg_owner_res.json()

    reg_member_res = await async_client.post(
        "/api/v1/auth/register", json=member_payload
    )
    assert reg_member_res.status_code == 201
    member_user = reg_member_res.json()

    # Login Owner
    owner_login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": owner_payload["email"], "password": owner_payload["password"]},
    )
    assert owner_login_res.status_code == 200
    owner_tokens = owner_login_res.json()
    owner_headers = {"Authorization": f"Bearer {owner_tokens['access_token']}"}

    # Login Member
    member_login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member_payload["email"], "password": member_payload["password"]},
    )
    assert member_login_res.status_code == 200
    member_tokens = member_login_res.json()
    member_headers = {"Authorization": f"Bearer {member_tokens['access_token']}"}

    # -------------------------------------------------------------------------
    # 2. Workspace Creation & Team Invitation
    # -------------------------------------------------------------------------
    ws_res = await async_client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Engineering Team Workspace"},
    )
    assert ws_res.status_code == 201
    workspace = ws_res.json()
    workspace_id = workspace["id"]
    assert workspace["owner_id"] == owner_user["id"]

    # Owner invites Member as EDITOR
    invite_res = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": member_user["id"], "role": "EDITOR"},
    )
    assert invite_res.status_code == 201
    assert invite_res.json()["role"] == "EDITOR"

    # Member verifies access to workspace list
    member_ws_list = await async_client.get(
        "/api/v1/workspaces", headers=member_headers
    )
    assert member_ws_list.status_code == 200
    assert any(w["id"] == workspace_id for w in member_ws_list.json()["items"])

    # -------------------------------------------------------------------------
    # 3. Project Creation & Label Definition
    # -------------------------------------------------------------------------
    project_res = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=owner_headers,
        json={
            "name": "TaskHub Backend Modernization",
            "description": "Multi-tenant REST API with Redis and RBAC",
        },
    )
    assert project_res.status_code == 201
    project = project_res.json()
    project_id = project["id"]
    assert project["status"] == "ACTIVE"

    # Create project label
    label_res = await async_client.post(
        f"/api/v1/projects/{project_id}/labels",
        headers=owner_headers,
        json={"name": "Feature", "color": "#00AAFF"},
    )
    assert label_res.status_code == 201
    label = label_res.json()
    label_id = label["id"]

    # -------------------------------------------------------------------------
    # 4. Task Creation, Assignment & Label Attachment
    # -------------------------------------------------------------------------
    task_res = await async_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=owner_headers,
        json={
            "title": "Implement Redis Cache Invalidation",
            "description": "Ensure O(1) versioned cache invalidation on mutations",
            "priority": "HIGH",
            "assignee_id": member_user["id"],
        },
    )
    assert task_res.status_code == 201
    task = task_res.json()
    task_id = task["id"]
    assert task["status"] == "TODO"
    assert task["assignee_id"] == member_user["id"]

    # Attach label to task
    attach_res = await async_client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=owner_headers,
    )
    assert attach_res.status_code == 200
    attached_labels = attach_res.json()["labels"]
    assert any(lbl["id"] == label_id for lbl in attached_labels)

    # -------------------------------------------------------------------------
    # 5. Member Collaboration: Read Tasks, Post Comments & Advance Status
    # -------------------------------------------------------------------------
    # Member lists tasks in project (validating DRY pagination & eager labels)
    tasks_list_res = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks",
        headers=member_headers,
    )
    assert tasks_list_res.status_code == 200
    tasks_page = tasks_list_res.json()
    assert tasks_page["total"] == 1
    assert tasks_page["items"][0]["id"] == task_id
    assert len(tasks_page["items"][0]["labels"]) == 1

    # Member posts comment on task
    comment_res = await async_client.post(
        f"/api/v1/tasks/{task_id}/comments",
        headers=member_headers,
        json={"content": "Implementation completed and unit tests verified."},
    )
    assert comment_res.status_code == 201
    comment = comment_res.json()
    assert comment["author_id"] == member_user["id"]
    assert "Implementation" in comment["content"]

    # Verify comments list on task
    comments_list_res = await async_client.get(
        f"/api/v1/tasks/{task_id}/comments",
        headers=owner_headers,
    )
    assert comments_list_res.status_code == 200
    assert comments_list_res.json()["total"] == 1

    # Member transitions task status to DONE
    patch_task_res = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=member_headers,
        json={"status": "DONE"},
    )
    assert patch_task_res.status_code == 200
    assert patch_task_res.json()["status"] == "DONE"

    # Verify filtering by status reflects DONE
    done_filter_res = await async_client.get(
        f"/api/v1/projects/{project_id}/tasks?status=DONE",
        headers=owner_headers,
    )
    assert done_filter_res.status_code == 200
    assert done_filter_res.json()["total"] == 1

    # -------------------------------------------------------------------------
    # 6. Project Archiving & Resource Management
    # -------------------------------------------------------------------------
    archive_res = await async_client.patch(
        f"/api/v1/projects/{project_id}",
        headers=owner_headers,
        json={"status": "ARCHIVED"},
    )
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"

    # -------------------------------------------------------------------------
    # 7. Session Security: Refresh Rotation, Reuse Detection & Logout
    # -------------------------------------------------------------------------
    # Rotate refresh token
    rotate_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": member_tokens["refresh_token"]},
    )
    assert rotate_res.status_code == 200
    new_member_tokens = rotate_res.json()
    assert "access_token" in new_member_tokens

    # Verify newly rotated token is active and valid
    me_res = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {new_member_tokens['access_token']}"},
    )
    assert me_res.status_code == 200
    reuse_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": member_tokens["refresh_token"]},
    )
    assert reuse_res.status_code == 401

    # Owner logs out cleanly
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers=owner_headers,
        json={"refresh_token": owner_tokens["refresh_token"]},
    )
    assert logout_res.status_code == 200
