"""Task management CRUD endpoints with authentication and RBAC."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Path, status

from app.core.dependencies import (
    CommentServiceDep,
    CurrentUser,
    LabelServiceDep,
    PaginationDep,
    TaskFilterDep,
    TaskServiceDep,
)
from app.schemas.base import PaginatedResponse
from app.schemas.comment import CommentCreate, CommentResponse
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


# ==============================================================================
# Task Labels Management
# ==============================================================================
@router.post(
    "/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign label to task",
    description="Assigns a project-scoped label to a task.",
)
async def attach_label(
    task_id: Annotated[int, Path(gt=0, description="Task ID")],
    label_id: Annotated[int, Path(gt=0, description="Label ID")],
    current_user: CurrentUser,
    service: LabelServiceDep,
) -> TaskResponse:
    """Assign label to task endpoint."""
    return await service.attach_label_to_task(
        task_id=task_id, label_id=label_id, current_user=current_user
    )


@router.delete(
    "/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove label from task",
    description="Removes an assigned label from a task.",
)
async def remove_label(
    task_id: Annotated[int, Path(gt=0, description="Task ID")],
    label_id: Annotated[int, Path(gt=0, description="Label ID")],
    current_user: CurrentUser,
    service: LabelServiceDep,
) -> TaskResponse:
    """Remove label from task endpoint."""
    return await service.remove_label_from_task(
        task_id=task_id, label_id=label_id, current_user=current_user
    )


# ==============================================================================
# Task Comments Management
# ==============================================================================
@router.post(
    "/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to task",
    description="Adds a new comment to a task (workspace members only).",
)
async def create_comment(
    task_id: Annotated[int, Path(gt=0, description="Task ID")],
    comment_in: CommentCreate,
    current_user: CurrentUser,
    service: CommentServiceDep,
) -> CommentResponse:
    """Add comment endpoint."""
    return await service.create_comment(
        task_id=task_id, comment_in=comment_in, current_user=current_user
    )


@router.get(
    "/{task_id}/comments",
    response_model=list[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List comments on task",
    description="Lists all comments on a task chronologically.",
)
async def list_comments(
    task_id: Annotated[int, Path(gt=0, description="Task ID")],
    current_user: CurrentUser,
    service: CommentServiceDep,
) -> list[CommentResponse]:
    """List comments endpoint."""
    return await service.list_comments(task_id=task_id, current_user=current_user)
