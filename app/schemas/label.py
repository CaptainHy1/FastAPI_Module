"""Label domain Pydantic schemas."""

from pydantic import Field, field_validator

from app.core.constants import (
    DEFAULT_LABEL_COLOR,
    MAX_LABEL_COLOR_LENGTH,
    MAX_LABEL_NAME_LENGTH,
    MIN_STRING_LENGTH,
)
from app.schemas.base import AppBaseModel


class LabelBase(AppBaseModel):
    """Base schema for task labels."""

    name: str = Field(
        ...,
        min_length=MIN_STRING_LENGTH,
        max_length=MAX_LABEL_NAME_LENGTH,
        description="Label name",
        examples=["backend", "bug", "feature"],
    )
    color: str = Field(
        default=DEFAULT_LABEL_COLOR,
        min_length=MAX_LABEL_COLOR_LENGTH,
        max_length=MAX_LABEL_COLOR_LENGTH,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Hexadecimal color string (e.g., #007BFF)",
        examples=["#007BFF", "#FF5733"],
    )


class LabelCreate(LabelBase):
    """Schema for creating a new label under a project."""

    @field_validator("name", mode="after")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure label name is not blank after whitespace stripping."""
        if not v.strip():
            raise ValueError("Label name cannot be empty.")
        return v.strip()


class LabelResponse(LabelBase):
    """Label representation returned to client."""

    id: int = Field(..., gt=0, description="Label ID")
    project_id: int = Field(..., gt=0, description="Project ID owning the label")
