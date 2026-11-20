"""Label repository layer."""

from sqlalchemy import CursorResult, delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.exceptions import ConflictException, NotFoundException
from app.models.task import Label, task_labels
from app.repositories.base import BaseRepository
from app.schemas.label import LabelCreate


class LabelRepository(BaseRepository[Label, LabelCreate, LabelCreate]):
    """Repository handling project-scoped labels and task-label associations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Label, db)

    async def create_label(self, project_id: int, name: str, color: str) -> Label:
        """Create a new label under a project, enforcing DB unique constraint."""
        label = Label(project_id=project_id, name=name, color=color)
        self.db.add(label)
        try:
            await self.db.commit()
            await self.db.refresh(label)
            return label
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException(message=messages.LABEL_ALREADY_EXISTS) from exc

    async def list_by_project(
        self,
        project_id: int,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Label], int]:
        """List labels defined within a project with deterministic ordering."""
        stmt = (
            select(Label)
            .where(Label.project_id == project_id)
            .order_by(Label.name.asc(), Label.id.asc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count(Label.id))
            .select_from(Label)
            .where(Label.project_id == project_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar_one())

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def attach_to_task(self, task_id: int, label_id: int) -> None:
        """Attach a label to a task, enforcing single assignment via primary key."""
        stmt = insert(task_labels).values(task_id=task_id, label_id=label_id)
        try:
            await self.db.execute(stmt)
            await self.db.commit()
            self.db.expire_all()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException(message=messages.LABEL_ALREADY_ATTACHED) from exc

    async def remove_from_task(self, task_id: int, label_id: int) -> None:
        """Remove a label from a task; raise NotFoundException if not attached."""
        stmt = (
            delete(task_labels)
            .where(
                (task_labels.c.task_id == task_id)
                & (task_labels.c.label_id == label_id)
            )
        )
        result = await self.db.execute(stmt)
        rowcount = result.rowcount if isinstance(result, CursorResult) else 0
        if rowcount == 0:
            raise NotFoundException(message=messages.LABEL_NOT_ATTACHED)
        await self.db.commit()
        self.db.expire_all()
