"""Task domain Pydantic v2 schemas."""

from datetime import datetime

from pydantic import Field

from app.core.constants import TaskPriority, TaskStatus
from app.schemas.base import AppBaseModel


class TaskBase(AppBaseModel):
    """Base attributes shared across task schemas."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Task title (cannot be empty)",
        examples=["Set up project layered architecture"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Detailed description of the task",
        examples=["Implement clean routers, services, repositories, and schemas."],
    )
    status: TaskStatus = Field(
        default=TaskStatus.TODO,
        description="Task status workflow state",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Priority level",
    )
    due_date: datetime | None = Field(
        default=None,
        description="Optional due date deadline for the task",
    )
    assignee_id: int | None = Field(
        default=None,
        gt=0,
        description="User ID assigned to complete this task",
    )


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    project_id: int = Field(
        ...,
        gt=0,
        description="Project ID that owns this task",
        examples=[1],
    )


class TaskUpdate(AppBaseModel):
    """Schema for updating an existing task (PATCH partial update)."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated title",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Updated description",
    )
    status: TaskStatus | None = Field(
        default=None,
        description="Updated status",
    )
    priority: TaskPriority | None = Field(
        default=None,
        description="Updated priority",
    )
    due_date: datetime | None = Field(
        default=None,
        description="Updated due date",
    )
    assignee_id: int | None = Field(
        default=None,
        gt=0,
        description="Updated assignee user ID",
    )


class TaskResponse(TaskBase):
    """Schema for task data returned to client."""

    id: int = Field(..., gt=0, description="Unique task identifier")
    project_id: int = Field(..., gt=0, description="Parent project identifier")
    created_by: int = Field(..., gt=0, description="User ID who created the task")
    created_at: datetime = Field(..., description="Timestamp when task was created")
    updated_at: datetime = Field(
        ..., description="Timestamp when task was last updated"
    )


class TaskFilterParams(AppBaseModel):
    """Optional query parameters for filtering tasks."""

    status: TaskStatus | None = Field(default=None, description="Filter by task status")
    priority: TaskPriority | None = Field(
        default=None, description="Filter by task priority"
    )
    project_id: int | None = Field(
        default=None, gt=0, description="Filter by project ID"
    )
    assignee_id: int | None = Field(
        default=None, gt=0, description="Filter by assignee user ID"
    )
    search: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Search term in title or description",
    )
