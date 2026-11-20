"""Project and project-scoped resource endpoints."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Path, status

from app.core.dependencies import (
    CurrentUser,
    PaginationDep,
    ProjectServiceDep,
    TaskFilterDep,
    TaskServiceDep,
)
from app.schemas.base import PaginatedResponse
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.schemas.task import TaskBase, TaskCreate, TaskResponse

router = APIRouter()


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project details",
    description="Retrieves project details if user is a workspace member or admin.",
)
async def get_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Get project details endpoint."""
    return await service.get_project_by_id(
        project_id=project_id, current_user=current_user
    )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
    description=(
        "Updates project name, description or status (OWNER/EDITOR or ADMIN only)."
    ),
)
async def update_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    project_in: ProjectUpdate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Update project endpoint."""
    return await service.update_project(
        project_id=project_id,
        project_in=project_in,
        current_user=current_user,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Deletes a project and its tasks (Workspace OWNER or ADMIN only).",
)
async def delete_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> None:
    """Delete project endpoint."""
    await service.delete_project(project_id=project_id, current_user=current_user)


# ==============================================================================
# Tasks Scoped to Project
# ==============================================================================
@router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task in project",
    description="Creates a new task in this project (OWNER/EDITOR or ADMIN only).",
)
async def create_task_in_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    task_in: TaskBase,
    current_user: CurrentUser,
    service: TaskServiceDep,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """Create task inside project endpoint."""
    task_create = TaskCreate(project_id=project_id, **task_in.model_dump())
    return await service.create_task(
        task_in=task_create,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.get(
    "/{project_id}/tasks",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List tasks in project",
    description="Lists tasks for a specific project with filtering and pagination.",
)
async def list_tasks_in_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    current_user: CurrentUser,
    pagination: PaginationDep,
    filters: TaskFilterDep,
    service: TaskServiceDep,
) -> PaginatedResponse[TaskResponse]:
    """List tasks inside project endpoint."""
    filters.project_id = project_id
    return await service.list_tasks(
        pagination=pagination,
        filters=filters,
        current_user=current_user,
    )
