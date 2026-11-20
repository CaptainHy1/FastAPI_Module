"""Project domain Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import Field, ValidationInfo, field_validator

from app.core.constants import (
    MAX_PROJECT_DESC_LENGTH,
    MAX_PROJECT_NAME_LENGTH,
    MIN_STRING_LENGTH,
    ProjectStatus,
)
from app.schemas.base import AppBaseModel


class ProjectBase(AppBaseModel):
    """Base attributes for project schemas."""

    name: str = Field(
        ...,
        min_length=MIN_STRING_LENGTH,
        max_length=MAX_PROJECT_NAME_LENGTH,
        description="Project name",
        examples=["TaskHub Backend API"],
    )
    description: str | None = Field(
        default=None,
        max_length=MAX_PROJECT_DESC_LENGTH,
        description="Detailed project description",
        examples=["Core API service and business workflows."],
    )


class ProjectCreate(ProjectBase):
    """Schema for creating a project inside a workspace."""

    pass


class ProjectUpdate(AppBaseModel):
    """Schema for partially updating a project."""

    name: str | None = Field(
        default=None,
        min_length=MIN_STRING_LENGTH,
        max_length=MAX_PROJECT_NAME_LENGTH,
        description="Updated project name",
    )
    description: str | None = Field(
        default=None,
        max_length=MAX_PROJECT_DESC_LENGTH,
        description="Updated project description",
    )
    status: ProjectStatus | None = Field(
        default=None,
        description="Updated project lifecycle status (ACTIVE, ARCHIVED)",
    )

    @field_validator("name", "status", mode="after")
    @classmethod
    def reject_null_for_non_nullable(cls, v: Any, info: ValidationInfo) -> Any:
        """Reject explicit null for non-nullable columns."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class ProjectResponse(ProjectBase):
    """Schema for project data returned to client."""

    id: int = Field(..., gt=0, description="Project ID")
    workspace_id: int = Field(..., gt=0, description="Parent workspace ID")
    status: ProjectStatus = Field(..., description="Project status")
    created_at: datetime = Field(..., description="Timestamp of project creation")
