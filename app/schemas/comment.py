"""Comment domain Pydantic schemas."""

from datetime import datetime

from pydantic import Field

from app.core.constants import MAX_COMMENT_LENGTH, MIN_STRING_LENGTH
from app.schemas.base import AppBaseModel


class CommentBase(AppBaseModel):
    """Base schema for task comments."""

    content: str = Field(
        ...,
        min_length=MIN_STRING_LENGTH,
        max_length=MAX_COMMENT_LENGTH,
        description="Comment text content",
        examples=["Task is progressing as expected."],
    )


class CommentCreate(CommentBase):
    """Schema for posting a comment."""


class CommentResponse(CommentBase):
    """Comment data returned to client."""

    id: int = Field(..., gt=0, description="Comment ID")
    task_id: int = Field(..., gt=0, description="Task ID")
    author_id: int = Field(..., gt=0, description="User ID of author")
    created_at: datetime = Field(..., description="Timestamp of comment creation")
    author_name: str | None = Field(
        default=None, description="Full name of comment author"
    )
    author_email: str | None = Field(
        default=None, description="Email of comment author"
    )
