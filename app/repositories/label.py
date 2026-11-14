"""Label repository layer."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import messages
from app.core.exceptions import ConflictException
from app.models.task import Label, Task
from app.repositories.base import BaseRepository
from app.schemas.label import LabelCreate


class LabelRepository(BaseRepository[Label, LabelCreate, LabelCreate]):
    """Repository handling project-scoped labels and task-label associations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Label, db)

    async def create_label(self, project_id: int, name: str, color: str) -> Label:
        """Create a new label under a project, preventing duplicate names."""
        existing_stmt = select(Label).where(
            Label.project_id == project_id, Label.name == name
        )
        existing = await self.db.execute(existing_stmt)
        if existing.scalars().first():
            raise ConflictException(message=messages.LABEL_ALREADY_EXISTS)

        label = Label(project_id=project_id, name=name, color=color)
        self.db.add(label)
        try:
            await self.db.commit()
            await self.db.refresh(label)
            return label
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException(message=messages.LABEL_ALREADY_EXISTS) from exc

    async def list_by_project(self, project_id: int) -> list[Label]:
        """List all labels defined within a project."""
        stmt = (
            select(Label)
            .where(Label.project_id == project_id)
            .order_by(Label.name.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def attach_to_task(self, task: Task, label: Label) -> None:
        """Attach a label to a task, enforcing single assignment."""
        # Ensure labels are loaded
        stmt = select(Task).where(Task.id == task.id).options(selectinload(Task.labels))
        refreshed_task = (await self.db.execute(stmt)).scalar_one()

        if any(existing.id == label.id for existing in refreshed_task.labels):
            raise ConflictException(message=messages.LABEL_ALREADY_ATTACHED)

        refreshed_task.labels.append(label)
        await self.db.commit()

    async def remove_from_task(self, task: Task, label: Label) -> None:
        """Remove a label from a task."""
        stmt = select(Task).where(Task.id == task.id).options(selectinload(Task.labels))
        refreshed_task = (await self.db.execute(stmt)).scalar_one()

        target = next(
            (item for item in refreshed_task.labels if item.id == label.id),
            None,
        )
        if not target:
            raise ConflictException(message=messages.LABEL_NOT_ATTACHED)

        refreshed_task.labels.remove(target)
        await self.db.commit()
