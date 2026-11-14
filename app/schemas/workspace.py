"""Workspace and WorkspaceMember Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import Field, ValidationInfo, field_validator

from app.core.constants import (
    MAX_WORKSPACE_NAME_LENGTH,
    MIN_STRING_LENGTH,
    WorkspaceRole,
)
from app.schemas.base import AppBaseModel


class WorkspaceBase(AppBaseModel):
    """Base workspace attributes."""

    name: str = Field(
        ...,
        min_length=MIN_STRING_LENGTH,
        max_length=MAX_WORKSPACE_NAME_LENGTH,
        description="Name of the workspace",
        examples=["Engineering Core"],
    )


class WorkspaceCreate(WorkspaceBase):
    """Schema for creating a new workspace."""

    pass


class WorkspaceUpdate(AppBaseModel):
    """Schema for updating a workspace."""

    name: str | None = Field(
        default=None,
        min_length=MIN_STRING_LENGTH,
        max_length=MAX_WORKSPACE_NAME_LENGTH,
        description="Updated name of the workspace",
    )

    @field_validator("name", mode="after")
    @classmethod
    def reject_null(cls, v: Any, info: ValidationInfo) -> Any:
        """Reject explicit null for non-nullable name."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class WorkspaceResponse(WorkspaceBase):
    """Workspace data returned to client."""

    id: int = Field(..., gt=0, description="Workspace ID")
    owner_id: int = Field(..., gt=0, description="User ID of the workspace owner")
    created_at: datetime = Field(..., description="Timestamp of workspace creation")


class WorkspaceMemberCreate(AppBaseModel):
    """Schema for adding/inviting a user to a workspace."""

    user_id: int = Field(
        ...,
        gt=0,
        description="ID of the user to add to the workspace",
        examples=[2],
    )
    role: WorkspaceRole = Field(
        default=WorkspaceRole.VIEWER,
        description="Role assigned to the user in this workspace",
    )


class WorkspaceMemberResponse(AppBaseModel):
    """Workspace member representation."""

    workspace_id: int = Field(..., gt=0, description="Workspace ID")
    user_id: int = Field(..., gt=0, description="User ID")
    role: WorkspaceRole = Field(..., description="Membership role")
    email: str | None = Field(
        default=None, description="User email (if loaded from relation)"
    )
    full_name: str | None = Field(
        default=None, description="User full name (if loaded from relation)"
    )
