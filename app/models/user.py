"""User ORM model definition."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    ENUM_COLUMN_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_FULL_NAME_LENGTH,
    MAX_PASSWORD_HASH_LENGTH,
    UserRole,
)
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import Comment, Task
    from app.models.workspace import Workspace, WorkspaceMember


class User(Base):
    """User account table."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(MAX_EMAIL_LENGTH), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(MAX_FULL_NAME_LENGTH), nullable=False)
    hashed_password: Mapped[str] = mapped_column(
        String(MAX_PASSWORD_HASH_LENGTH), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, length=ENUM_COLUMN_LENGTH),
        default=UserRole.MEMBER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    owned_workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    workspace_memberships: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    created_tasks: Mapped[list["Task"]] = relationship(
        foreign_keys="Task.created_by",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    assigned_tasks: Mapped[list["Task"]] = relationship(
        foreign_keys="Task.assignee_id",
        back_populates="assignee",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
