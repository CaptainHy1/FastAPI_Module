"""Tests for task CRUD endpoints and validation."""

import pytest
from httpx import AsyncClient


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
