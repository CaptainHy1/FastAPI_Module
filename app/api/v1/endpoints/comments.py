"""Comment endpoints for task discussion."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.core.dependencies import (
    CommentServiceDep,
    CurrentUser,
    PaginationDep,
)
from app.schemas.base import PaginatedResponse
from app.schemas.comment import CommentCreate, CommentResponse

router = APIRouter()


@router.post(
    "/tasks/{task_id}/comments",
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
    "/tasks/{task_id}/comments",
    response_model=PaginatedResponse[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List comments on task",
    description="Lists all comments on a task chronologically with pagination.",
)
async def list_comments(
    task_id: Annotated[int, Path(gt=0, description="Task ID")],
    current_user: CurrentUser,
    pagination: PaginationDep,
    service: CommentServiceDep,
) -> PaginatedResponse[CommentResponse]:
    """List comments endpoint."""
    return await service.list_comments(
        task_id=task_id, current_user=current_user, pagination=pagination
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
    description="Deletes a task comment (author or workspace owner only).",
)
async def delete_comment(
    comment_id: Annotated[int, Path(gt=0, description="Comment ID")],
    current_user: CurrentUser,
    service: CommentServiceDep,
) -> None:
    """Delete comment endpoint."""
    await service.delete_comment(comment_id=comment_id, current_user=current_user)
