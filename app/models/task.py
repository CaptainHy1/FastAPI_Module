"""Task, Label, task_labels, and Comment ORM model definitions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    DEFAULT_LABEL_COLOR,
    ENUM_COLUMN_LENGTH,
    MAX_COMMENT_LENGTH,
    MAX_LABEL_COLOR_LENGTH,
    MAX_LABEL_NAME_LENGTH,
    MAX_TASK_DESC_LENGTH,
    MAX_TASK_TITLE_LENGTH,
    TaskPriority,
    TaskStatus,
)
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User

# Association table linking Tasks and Labels (many-to-many)
task_labels = Table(
    "task_labels",
    Base.metadata,
    Column(
        "task_id",
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "label_id",
        ForeignKey("labels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Task(Base):
    """Task entity within a project."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(MAX_TASK_TITLE_LENGTH), nullable=False)
    description: Mapped[str | None] = mapped_column(
        String(MAX_TASK_DESC_LENGTH), nullable=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=ENUM_COLUMN_LENGTH),
        default=TaskStatus.TODO,
        nullable=False,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority, native_enum=False, length=ENUM_COLUMN_LENGTH),
        default=TaskPriority.MEDIUM,
        nullable=False,
        index=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="tasks")
    assignee: Mapped["User | None"] = relationship(
        foreign_keys=[assignee_id], back_populates="assigned_tasks"
    )
    creator: Mapped["User"] = relationship(
        foreign_keys=[created_by], back_populates="created_tasks"
    )
    labels: Mapped[list["Label"]] = relationship(
        secondary=task_labels, back_populates="tasks"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class Label(Base):
    """Project-scoped tag/label for categorizing tasks."""

    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(MAX_LABEL_NAME_LENGTH), nullable=False)
    color: Mapped[str] = mapped_column(
        String(MAX_LABEL_COLOR_LENGTH), default=DEFAULT_LABEL_COLOR, nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="labels")
    tasks: Mapped[list["Task"]] = relationship(
        secondary=task_labels, back_populates="labels"
    )


class Comment(Base):
    """User comment on a task."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(String(MAX_COMMENT_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")
