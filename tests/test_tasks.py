"""Tests for task CRUD endpoints, database integration, and ORM relationships."""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import messages
from app.core.config import Settings
from app.models import Comment, Label, Project, Task, User, Workspace


@pytest.mark.asyncio
async def test_create_task_success(async_client: AsyncClient) -> None:
    """Test creating a valid task with whitespace stripping."""
    payload = {
        "title": "  Setup Layered Architecture  ",
        "description": "  Detailed task description  ",
        "project_id": 1,
        "priority": "HIGH",
        "status": "TODO",
    }
    response = await async_client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    # Check that whitespace was stripped
    assert data["title"] == "Setup Layered Architecture"
    assert data["description"] == "Detailed task description"
    assert data["priority"] == "HIGH"
    assert data["status"] == "TODO"
    assert data["project_id"] == 1
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_task_validation_failure(async_client: AsyncClient) -> None:
    """Test validation errors return 422 with uniform JSON error structure."""
    # Missing required title and project_id
    payload = {"description": "Missing title"}
    response = await async_client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == 422
    assert "details" in data["error"]


@pytest.mark.asyncio
async def test_get_task_by_id_success(async_client: AsyncClient) -> None:
    """Test retrieving existing task."""
    created = await async_client.post(
        "/api/v1/tasks",
        json={"title": "Test Task", "project_id": 1},
    )
    task_id = created.json()["id"]

    response = await async_client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Test Task"


@pytest.mark.asyncio
async def test_get_task_not_found_returns_custom_error(
    async_client: AsyncClient,
) -> None:
    """Test that missing resource returns 404 with custom AppException envelope."""
    response = await async_client.get("/api/v1/tasks/9999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == 404
    assert data["error"]["message"] == "Task not found."


@pytest.mark.asyncio
async def test_list_tasks_with_pagination(async_client: AsyncClient) -> None:
    """Test paginated task listing and metadata."""
    for i in range(15):
        await async_client.post(
            "/api/v1/tasks",
            json={"title": f"Task #{i + 1}", "project_id": 1},
        )

    # Fetch page 1 (size 10)
    response = await async_client.get("/api/v1/tasks?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 2
    assert len(data["items"]) == 10

    # Fetch page 2 (size 10)
    response2 = await async_client.get("/api/v1/tasks?page=2&page_size=10")
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 5


@pytest.mark.asyncio
async def test_list_tasks_filtered_by_status(async_client: AsyncClient) -> None:
    """Test filtering tasks by status."""
    await async_client.post(
        "/api/v1/tasks",
        json={"title": "Todo Task", "status": "TODO", "project_id": 1},
    )
    await async_client.post(
        "/api/v1/tasks",
        json={"title": "Done Task", "status": "DONE", "project_id": 1},
    )

    response = await async_client.get("/api/v1/tasks?status=DONE")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Done Task"


@pytest.mark.asyncio
async def test_update_task_patch(async_client: AsyncClient) -> None:
    """Test partial update of a task."""
    created = await async_client.post(
        "/api/v1/tasks",
        json={"title": "Initial Title", "status": "TODO", "project_id": 1},
    )
    task_id = created.json()["id"]

    update_payload = {"status": "IN_PROGRESS", "priority": "URGENT"}
    response = await async_client.patch(f"/api/v1/tasks/{task_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Initial Title"  # Unchanged
    assert data["status"] == "IN_PROGRESS"
    assert data["priority"] == "URGENT"


@pytest.mark.asyncio
async def test_delete_task(async_client: AsyncClient) -> None:
    """Test deleting task returns 204 then 404 upon next query."""
    created = await async_client.post(
        "/api/v1/tasks",
        json={"title": "To be deleted", "project_id": 1},
    )
    task_id = created.json()["id"]

    delete_resp = await async_client.delete(f"/api/v1/tasks/{task_id}")
    assert delete_resp.status_code == 204

    get_resp = await async_client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_task_invalid_project_returns_400(
    async_client: AsyncClient,
) -> None:
    """Test creating a task with nonexistent project_id handles IntegrityError."""
    payload = {
        "title": "Orphan Task",
        "project_id": 9999,
    }
    response = await async_client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == 400
    assert data["error"]["message"] == messages.INVALID_REFERENCE


@pytest.mark.asyncio
async def test_list_tasks_search_and_priority_filter(
    async_client: AsyncClient,
) -> None:
    """Test filtering by priority and case-insensitive search."""
    await async_client.post(
        "/api/v1/tasks",
        json={
            "title": "Fix Alembic Migration",
            "priority": "URGENT",
            "project_id": 1,
        },
    )
    await async_client.post(
        "/api/v1/tasks",
        json={
            "title": "Write Docs",
            "priority": "LOW",
            "project_id": 1,
        },
    )

    response = await async_client.get("/api/v1/tasks?priority=URGENT&search=alembic")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Fix Alembic Migration"


@pytest.mark.asyncio
async def test_orm_relationships(db_session: AsyncSession) -> None:
    """Verify bidirectional SQLAlchemy 2.x relationships across all core entities."""
    task = Task(
        project_id=1,
        created_by=1,
        assignee_id=1,
        title="Relationship Check",
    )
    label = Label(project_id=1, name="backend", color="#10B981")
    task.labels.append(label)
    db_session.add(task)
    await db_session.flush()

    comment = Comment(task_id=task.id, author_id=1, content="Looks good!")
    db_session.add(comment)
    await db_session.commit()

    stmt = (
        select(Task)
        .where(Task.id == task.id)
        .options(
            selectinload(Task.project)
            .selectinload(Project.workspace)
            .selectinload(Workspace.owner),
            selectinload(Task.creator),
            selectinload(Task.assignee),
            selectinload(Task.labels),
            selectinload(Task.comments).selectinload(Comment.author),
        )
    )
    loaded = (await db_session.execute(stmt)).scalar_one()

    assert loaded.project.name == "TaskHub Core"
    assert loaded.project.workspace.name == "Default Workspace"
    assert loaded.project.workspace.owner.email == "demo@taskhub.dev"
    assert isinstance(loaded.creator, User)
    assert loaded.assignee is not None and loaded.assignee.id == 1
    assert len(loaded.labels) == 1
    assert loaded.labels[0].name == "backend"
    assert len(loaded.comments) == 1
    assert loaded.comments[0].content == "Looks good!"


@pytest.mark.asyncio
async def test_update_task_null_on_not_null_fields_returns_422(
    async_client: AsyncClient,
) -> None:
    """Test sending null to NOT NULL columns in PATCH returns 422, never 500."""
    created = await async_client.post(
        "/api/v1/tasks",
        json={"title": "Valid Task", "project_id": 1},
    )
    task_id = created.json()["id"]

    for field in ("title", "status", "priority"):
        response = await async_client.patch(
            f"/api/v1/tasks/{task_id}",
            json={field: None},
        )
        assert response.status_code == 422, f"Expected 422 for {field}=null"
        data = response.json()
        assert data["error"]["code"] == 422


@pytest.mark.asyncio
async def test_update_task_null_on_nullable_fields_succeeds(
    async_client: AsyncClient,
) -> None:
    """Test clearing nullable columns (description, assignee_id) returns 200."""
    created = await async_client.post(
        "/api/v1/tasks",
        json={
            "title": "Nullable Check",
            "description": "Some notes",
            "assignee_id": 1,
            "project_id": 1,
        },
    )
    task_id = created.json()["id"]

    response = await async_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"description": None, "assignee_id": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] is None
    assert data["assignee_id"] is None


def test_settings_rejects_whitespace_secret_key() -> None:
    """Test Settings fails fast if SECRET_KEY is empty or whitespace-only."""
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY=" " * 32)
