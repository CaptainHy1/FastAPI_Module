"""Workspace and WorkspaceMember ORM model definitions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    ENUM_COLUMN_LENGTH,
    MAX_WORKSPACE_NAME_LENGTH,
    WorkspaceRole,
)
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Workspace(Base):
    """Workspace table grouping projects and team members."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(MAX_WORKSPACE_NAME_LENGTH), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="owned_workspaces")
    members: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(Base):
    """Association model linking Users to Workspaces with a role."""

    __tablename__ = "workspace_members"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(WorkspaceRole, native_enum=False, length=ENUM_COLUMN_LENGTH),
        default=WorkspaceRole.VIEWER,
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="workspace_memberships")
