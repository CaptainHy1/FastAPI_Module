"""Project ORM model definition."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    ENUM_COLUMN_LENGTH,
    MAX_PROJECT_DESC_LENGTH,
    MAX_PROJECT_NAME_LENGTH,
    ProjectStatus,
)
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import Label, Task
    from app.models.workspace import Workspace


class Project(Base):
    """Project table containing tasks and labels inside a workspace."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(MAX_PROJECT_NAME_LENGTH), nullable=False)
    description: Mapped[str | None] = mapped_column(
        String(MAX_PROJECT_DESC_LENGTH), nullable=True
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, native_enum=False, length=ENUM_COLUMN_LENGTH),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    labels: Mapped[list["Label"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
