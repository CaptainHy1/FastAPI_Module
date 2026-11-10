"""Base Pydantic schemas and generic response models."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")


class AppBaseModel(BaseModel):
    """Base schema for all models in TaskHub.

    - Automatically strips leading and trailing whitespace from string fields.
    - Enables ORM / attribute population (Pydantic v2 from_attributes).
    - Populates by field name or alias.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
        from_attributes=True,
    )


class PaginationParams(AppBaseModel):
    """Query parameters for paginated endpoints."""

    page: int = Field(default=DEFAULT_PAGE, ge=1, description="Page number (1-based)")
    page_size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of items per page",
    )

    @property
    def skip(self) -> int:
        """Calculate offset for queries."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Alias for page_size limit."""
        return self.page_size


class PaginatedResponse(AppBaseModel, Generic[T]):
    """Standardized paginated list response wrapper."""

    items: list[T]
    total: int = Field(..., ge=0, description="Total number of items matching filter")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class ErrorDetail(AppBaseModel):
    """Structured error detail representation."""

    code: int
    message: str
    details: list[dict[str, str]] | dict[str, str] | None = None


class ErrorResponse(AppBaseModel):
    """Top-level error response envelope for OpenAPI documentation."""

    error: ErrorDetail
