"""Label standalone endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.core.dependencies import CurrentUser, LabelServiceDep

router = APIRouter()


@router.delete(
    "/{label_id}",
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
