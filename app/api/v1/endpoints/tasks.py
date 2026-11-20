"""Task management CRUD endpoints with authentication and RBAC."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Path, status

from app.core.dependencies import (
    CurrentUser,
    PaginationDep,
    TaskFilterDep,
    TaskServiceDep,
)
from app.core.openapi import build_error_responses
from app.schemas.base import PaginatedResponse
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Create a new task",
    description=(
        "Creates a new task assigned to a project and returns the created task."
    ),
)
async def create_task(
    task_in: TaskCreate,
    current_user: CurrentUser,
    service: TaskServiceDep,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Create task endpoint."""
    return await service.create_task(
        task_in=task_in,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.get(
    "",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(status.HTTP_401_UNAUTHORIZED),
    summary="List tasks",
    description=(
        "Retrieves a paginated list of tasks with optional filters "
        "by status, priority, etc."
    ),
)
async def list_tasks(
    current_user: CurrentUser,
    service: TaskServiceDep,
    pagination: PaginationDep,
    filters: TaskFilterDep,
) -> PaginatedResponse[TaskResponse]:
    """List paginated tasks endpoint."""
    return await service.list_tasks(
        pagination=pagination, filters=filters, current_user=current_user
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Get task details",
    description="Retrieves details of a single task by its unique ID.",
)
async def get_task(
    task_id: Annotated[int, Path(gt=0, description="Task ID", examples=[1])],
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """Get single task by ID."""
    return await service.get_task_by_id(task_id=task_id, current_user=current_user)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Update a task",
    description=(
        "Partially updates an existing task (title, description, status, priority)."
    ),
)
async def update_task(
    task_id: Annotated[int, Path(gt=0, description="Task ID", examples=[1])],
    task_in: TaskUpdate,
    current_user: CurrentUser,
    service: TaskServiceDep,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Partial update task endpoint."""
    return await service.update_task(
        task_id=task_id,
        task_in=task_in,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Delete a task",
    description="Deletes a task by its ID.",
)
async def delete_task(
    task_id: Annotated[int, Path(gt=0, description="Task ID", examples=[1])],
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> None:
    """Delete task endpoint."""
    await service.delete_task(task_id=task_id, current_user=current_user)
