"""Label endpoints including project-scoped creation and task association."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.core.dependencies import (
    CurrentUser,
    LabelServiceDep,
    PaginationDep,
)
from app.schemas.base import PaginatedResponse
from app.schemas.label import LabelCreate, LabelResponse
from app.schemas.task import TaskResponse

router = APIRouter()


@router.post(
    "/projects/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create label in project",
    description="Creates a new label within this project (OWNER/EDITOR or ADMIN only).",
)
async def create_label_in_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    label_in: LabelCreate,
    current_user: CurrentUser,
    service: LabelServiceDep,
) -> LabelResponse:
    """Create label in project endpoint."""
    return await service.create_label(
        project_id=project_id,
        label_in=label_in,
        current_user=current_user,
    )


@router.get(
    "/projects/{project_id}/labels",
    response_model=PaginatedResponse[LabelResponse],
    status_code=status.HTTP_200_OK,
    summary="List labels in project",
    description="Lists all labels defined for this project (members or ADMIN).",
)
async def list_labels_in_project(
    project_id: Annotated[int, Path(gt=0, description="Project ID")],
    current_user: CurrentUser,
    pagination: PaginationDep,
    service: LabelServiceDep,
) -> PaginatedResponse[LabelResponse]:
    """List labels in project endpoint."""
    return await service.list_labels(
        project_id=project_id,
        current_user=current_user,
        pagination=pagination,
    )


@router.post(
    "/tasks/{task_id}/labels/{label_id}",
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
    "/tasks/{task_id}/labels/{label_id}",
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


@router.delete(
    "/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a label",
    description="Deletes a project label (OWNER/EDITOR or ADMIN only).",
)
async def delete_label(
    label_id: Annotated[int, Path(gt=0, description="Label ID")],
    current_user: CurrentUser,
    service: LabelServiceDep,
) -> None:
    """Delete label endpoint."""
    await service.delete_label(label_id=label_id, current_user=current_user)
