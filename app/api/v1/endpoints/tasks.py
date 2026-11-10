"""Task management CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.core.dependencies import PaginationDep, TaskFilterDep, TaskServiceDep
from app.schemas.base import PaginatedResponse
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description=(
        "Creates a new task assigned to a project and returns the created task."
    ),
)
async def create_task(
    task_in: TaskCreate,
    service: TaskServiceDep,
) -> TaskResponse:
    """Create task endpoint."""
    return await service.create_task(task_in=task_in)


@router.get(
    "",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List tasks",
    description=(
        "Retrieves a paginated list of tasks with optional filters "
        "by status, priority, etc."
    ),
)
async def list_tasks(
    service: TaskServiceDep,
    pagination: PaginationDep,
    filters: TaskFilterDep,
) -> PaginatedResponse[TaskResponse]:
    """List paginated tasks endpoint."""
    return await service.list_tasks(pagination=pagination, filters=filters)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get task details",
    description="Retrieves details of a single task by its unique ID.",
)
async def get_task(
    task_id: Annotated[int, Path(gt=0, description="Task ID", examples=[1])],
    service: TaskServiceDep,
) -> TaskResponse:
    """Get single task by ID."""
    return await service.get_task_by_id(task_id)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a task",
    description=(
        "Partially updates an existing task (title, description, status, priority)."
    ),
)
async def update_task(
    task_id: Annotated[int, Path(gt=0, description="Task ID", examples=[1])],
    task_in: TaskUpdate,
    service: TaskServiceDep,
) -> TaskResponse:
    """Partial update task endpoint."""
    return await service.update_task(task_id=task_id, task_in=task_in)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description="Deletes a task by its ID.",
)
async def delete_task(
    task_id: Annotated[int, Path(gt=0, description="Task ID", examples=[1])],
    service: TaskServiceDep,
) -> None:
    """Delete task endpoint."""
    await service.delete_task(task_id)
