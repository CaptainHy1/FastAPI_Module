"""Comment standalone endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.core.dependencies import CommentServiceDep, CurrentUser

router = APIRouter()


@router.delete(
    "/{comment_id}",
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
