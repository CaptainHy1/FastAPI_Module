"""Tests for Day 5: Task features, labels, comments, and filtering."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core import messages
from app.core.constants import TaskPriority, TaskStatus, WorkspaceRole


async def _register_user(client: AsyncClient, email: str, name: str) -> dict[str, str]:
    """Register, login and return Authorization Bearer headers."""
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
async def test_labels_crud_and_rbac(async_client: AsyncClient) -> None:
    """Test creating, listing, and deleting project labels with role enforcement."""
    owner_hdrs = await _register_user(async_client, "lbl_owner@taskhub.dev", "Owner")
    editor_hdrs = await _register_user(async_client, "lbl_editor@taskhub.dev", "Editor")
    viewer_hdrs = await _register_user(async_client, "lbl_viewer@taskhub.dev", "Viewer")

    ed_profile = (
        await async_client.get("/api/v1/users/me", headers=editor_hdrs)
    ).json()
    vw_profile = (
        await async_client.get("/api/v1/users/me", headers=viewer_hdrs)
    ).json()

    # Create workspace and project
    ws = (
        await async_client.post(
            "/api/v1/workspaces",
            json={"name": "Label WS"},
            headers=owner_hdrs,
        )
    ).json()
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": ed_profile["id"], "role": WorkspaceRole.EDITOR},
        headers=owner_hdrs,
    )
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": vw_profile["id"], "role": WorkspaceRole.VIEWER},
        headers=owner_hdrs,
    )

    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Label Proj"},
            headers=owner_hdrs,
        )
    ).json()
    proj_id = proj["id"]

    # Viewer cannot create label -> 403
    vw_lbl = await async_client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "bug", "color": "#FF0000"},
        headers=viewer_hdrs,
    )
    assert vw_lbl.status_code == 403

    # Editor can create label -> 201
    ed_lbl = await async_client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "backend", "color": "#10B981"},
        headers=editor_hdrs,
    )
    assert ed_lbl.status_code == 201
    lbl_data = ed_lbl.json()
    assert lbl_data["name"] == "backend"
    assert lbl_data["color"] == "#10B981"
    label_id = lbl_data["id"]

    # Duplicate label name in same project -> 409
    dup_lbl = await async_client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "backend", "color": "#0000FF"},
        headers=editor_hdrs,
    )
    assert dup_lbl.status_code == 409
    assert dup_lbl.json()["error"]["message"] == messages.LABEL_ALREADY_EXISTS

    # Viewer can list labels -> 200 (PaginatedResponse)
    list_res = await async_client.get(
        f"/api/v1/projects/{proj_id}/labels", headers=viewer_hdrs
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert len(list_res.json()["items"]) == 1

    # Viewer cannot delete label -> 403
    del_vw = await async_client.delete(
        f"/api/v1/labels/{label_id}", headers=viewer_hdrs
    )
    assert del_vw.status_code == 403

    # Editor can delete label -> 204
    del_ed = await async_client.delete(
        f"/api/v1/labels/{label_id}", headers=editor_hdrs
    )
    assert del_ed.status_code == 204


@pytest.mark.asyncio
async def test_task_label_attach_and_detach(async_client: AsyncClient) -> None:
    """Test assigning and removing labels on tasks across projects."""
    owner_hdrs = await _register_user(
        async_client, "task_lbl_owner@taskhub.dev", "Owner"
    )

    # Setup Workspace & 2 Projects
    ws = (
        await async_client.post(
            "/api/v1/workspaces",
            json={"name": "MultiProj WS"},
            headers=owner_hdrs,
        )
    ).json()

    p1 = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Project 1"},
            headers=owner_hdrs,
        )
    ).json()
    p2 = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Project 2"},
            headers=owner_hdrs,
        )
    ).json()

    lbl_p1 = (
        await async_client.post(
            f"/api/v1/projects/{p1['id']}/labels",
            json={"name": "P1-Label", "color": "#112233"},
            headers=owner_hdrs,
        )
    ).json()

    lbl_p2 = (
        await async_client.post(
            f"/api/v1/projects/{p2['id']}/labels",
            json={"name": "P2-Label", "color": "#445566"},
            headers=owner_hdrs,
        )
    ).json()

    task_p1 = (
        await async_client.post(
            f"/api/v1/projects/{p1['id']}/tasks",
            json={"title": "P1 Task"},
            headers=owner_hdrs,
        )
    ).json()

    # Attach cross-project label (Label from P2 to Task in P1) -> 400
    cross_res = await async_client.post(
        f"/api/v1/tasks/{task_p1['id']}/labels/{lbl_p2['id']}",
        headers=owner_hdrs,
    )
    assert cross_res.status_code == 400
    assert cross_res.json()["error"]["message"] == messages.LABEL_PROJECT_MISMATCH

    # Attach valid label -> 200
    attach_res = await async_client.post(
        f"/api/v1/tasks/{task_p1['id']}/labels/{lbl_p1['id']}",
        headers=owner_hdrs,
    )
    assert attach_res.status_code == 200
    attached_task = attach_res.json()
    assert len(attached_task["labels"]) == 1
    assert attached_task["labels"][0]["name"] == "P1-Label"

    # Duplicate attach -> 409
    dup_attach = await async_client.post(
        f"/api/v1/tasks/{task_p1['id']}/labels/{lbl_p1['id']}",
        headers=owner_hdrs,
    )
    assert dup_attach.status_code == 409
    assert dup_attach.json()["error"]["message"] == messages.LABEL_ALREADY_ATTACHED

    # Detach label -> 200
    detach_res = await async_client.delete(
        f"/api/v1/tasks/{task_p1['id']}/labels/{lbl_p1['id']}",
        headers=owner_hdrs,
    )
    assert detach_res.status_code == 200
    assert len(detach_res.json()["labels"]) == 0

    # Detach unattached label -> 404 (Item 4)
    del_unattached = await async_client.delete(
        f"/api/v1/tasks/{task_p1['id']}/labels/{lbl_p1['id']}",
        headers=owner_hdrs,
    )
    assert del_unattached.status_code == 404
    assert del_unattached.json()["error"]["message"] == messages.LABEL_NOT_ATTACHED

    # Assignee with only VIEWER role cannot attach/detach label -> 403 (Item 5)
    viewer_user_hdrs = await _register_user(
        async_client, "viewer_assignee@taskhub.dev", "ViewerAssignee"
    )
    viewer_id = (
        await async_client.get("/api/v1/users/me", headers=viewer_user_hdrs)
    ).json()["id"]
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": viewer_id, "role": WorkspaceRole.VIEWER},
        headers=owner_hdrs,
    )
    task_for_viewer = (
        await async_client.post(
            f"/api/v1/projects/{p1['id']}/tasks",
            json={"title": "Viewer Assigned Task", "assignee_id": viewer_id},
            headers=owner_hdrs,
        )
    ).json()

    vw_attach = await async_client.post(
        f"/api/v1/tasks/{task_for_viewer['id']}/labels/{lbl_p1['id']}",
        headers=viewer_user_hdrs,
    )
    assert vw_attach.status_code == 403
    assert vw_attach.json()["error"]["message"] == messages.TASK_EDITOR_REQUIRED


@pytest.mark.asyncio
async def test_comments_crud_and_rbac(async_client: AsyncClient) -> None:
    """Test adding comments, listing comments, and authorization on comment deletion."""
    owner_hdrs = await _register_user(async_client, "cmt_owner@taskhub.dev", "Owner")
    member_hdrs = await _register_user(async_client, "cmt_member@taskhub.dev", "Member")
    other_hdrs = await _register_user(async_client, "cmt_other@taskhub.dev", "Other")

    mem_id = (await async_client.get("/api/v1/users/me", headers=member_hdrs)).json()[
        "id"
    ]

    ws = (
        await async_client.post(
            "/api/v1/workspaces",
            json={"name": "Comment WS"},
            headers=owner_hdrs,
        )
    ).json()
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": mem_id, "role": WorkspaceRole.VIEWER},
        headers=owner_hdrs,
    )

    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Comment Proj"},
            headers=owner_hdrs,
        )
    ).json()

    task = (
        await async_client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={"title": "Comment Task"},
            headers=owner_hdrs,
        )
    ).json()

    # Non-workspace user cannot comment -> 403
    out_cmt = await async_client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"content": "Malicious comment"},
        headers=other_hdrs,
    )
    assert out_cmt.status_code == 403

    # Member can comment -> 201
    cmt_res = await async_client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"content": "Here is my update on this task."},
        headers=member_hdrs,
    )
    assert cmt_res.status_code == 201
    cmt_id = cmt_res.json()["id"]
    assert cmt_res.json()["content"] == "Here is my update on this task."

    # Blank content returns 422
    blank_cmt = await async_client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"content": "   "},
        headers=member_hdrs,
    )
    assert blank_cmt.status_code == 422

    # List comments -> 200 (PaginatedResponse)
    list_cmt = await async_client.get(
        f"/api/v1/tasks/{task['id']}/comments", headers=owner_hdrs
    )
    assert list_cmt.status_code == 200
    assert list_cmt.json()["total"] == 1
    assert len(list_cmt.json()["items"]) == 1

    # Another member cannot delete this comment -> 403
    del_other = await async_client.delete(
        f"/api/v1/comments/{cmt_id}", headers=other_hdrs
    )
    assert del_other.status_code == 403

    # Workspace Owner can delete comment -> 204
    del_owner = await async_client.delete(
        f"/api/v1/comments/{cmt_id}", headers=owner_hdrs
    )
    assert del_owner.status_code == 204


@pytest.mark.asyncio
async def test_task_assignment_validation_and_status_transitions(
    async_client: AsyncClient,
) -> None:
    """Assignee must belong to workspace; status transitions and filtering work."""
    owner_hdrs = await _register_user(async_client, "assign_owner@taskhub.dev", "Owner")
    member_hdrs = await _register_user(
        async_client, "assign_member@taskhub.dev", "Member"
    )
    outsider_hdrs = await _register_user(
        async_client, "assign_out@taskhub.dev", "Outsider"
    )

    mem_id = (await async_client.get("/api/v1/users/me", headers=member_hdrs)).json()[
        "id"
    ]
    out_id = (await async_client.get("/api/v1/users/me", headers=outsider_hdrs)).json()[
        "id"
    ]

    ws = (
        await async_client.post(
            "/api/v1/workspaces",
            json={"name": "Assign WS"},
            headers=owner_hdrs,
        )
    ).json()
    await async_client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": mem_id, "role": WorkspaceRole.EDITOR},
        headers=owner_hdrs,
    )

    proj = (
        await async_client.post(
            f"/api/v1/workspaces/{ws['id']}/projects",
            json={"name": "Assign Proj"},
            headers=owner_hdrs,
        )
    ).json()

    # Assign to non-member outsider -> 422
    bad_assign = await async_client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Invalid Assign", "assignee_id": out_id},
        headers=owner_hdrs,
    )
    assert bad_assign.status_code == 422
    assert (
        bad_assign.json()["error"]["message"] == messages.ASSIGNEE_NOT_WORKSPACE_MEMBER
    )

    # Assign to valid member -> 201
    future_date = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    task = (
        await async_client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={
                "title": "Valid Task",
                "assignee_id": mem_id,
                "priority": TaskPriority.HIGH,
                "due_date": future_date,
            },
            headers=owner_hdrs,
        )
    ).json()
    assert task["assignee_id"] == mem_id
    assert task["status"] == TaskStatus.TODO

    # Assignee updates status to IN_PROGRESS and then DONE -> 200
    s1 = await async_client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": TaskStatus.IN_PROGRESS},
        headers=member_hdrs,
    )
    assert s1.status_code == 200
    assert s1.json()["status"] == TaskStatus.IN_PROGRESS

    s2 = await async_client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": TaskStatus.DONE},
        headers=member_hdrs,
    )
    assert s2.status_code == 200
    assert s2.json()["status"] == TaskStatus.DONE

    # Advanced filtering on GET /projects/{id}/tasks with multiple statuses
    filter_res = await async_client.get(
        f"/api/v1/projects/{proj['id']}/tasks?status=DONE&status=IN_PROGRESS&priority=HIGH&assignee_id={mem_id}",
        headers=member_hdrs,
    )
    assert filter_res.status_code == 200
    assert filter_res.json()["total"] == 1
    assert filter_res.json()["items"][0]["id"] == task["id"]

    # Filter with non-matching status list
    filter_res_empty = await async_client.get(
        f"/api/v1/projects/{proj['id']}/tasks?status=TODO",
        headers=member_hdrs,
    )
    assert filter_res_empty.status_code == 200
    assert filter_res_empty.json()["total"] == 0

    # Search with special characters test
    search_res = await async_client.get(
        f"/api/v1/projects/{proj['id']}/tasks?search=Valid%20Task",
        headers=member_hdrs,
    )
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
