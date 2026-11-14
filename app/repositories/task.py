"""Task repository implementation using SQLAlchemy 2.x async."""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository(BaseRepository[Task, TaskCreate, TaskUpdate]):
    """Async repository for Task CRUD, filtering, and pagination."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=Task, db=db)

    async def get_by_id(self, id_: Any) -> Task | None:
        """Retrieve a single task with labels eagerly loaded."""
        stmt = select(Task).where(Task.id == id_).options(selectinload(Task.labels))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, obj_in: TaskCreate, **extra_fields: Any) -> Task:
        """Create a task and return with labels eagerly loaded."""
        task = await super().create(obj_in, **extra_fields)
        refreshed = await self.get_by_id(task.id)
        return refreshed or task

    async def update(self, id_: Any, obj_in: TaskUpdate, **kwargs: Any) -> Task | None:
        """Update a task and return with labels eagerly loaded."""
        task = await super().update(id_, obj_in, **kwargs)
        if task:
            return await self.get_by_id(id_)
        return None

    async def list_items(
        self,
        skip: int = 0,
        limit: int = 10,
        **kwargs: Any,
    ) -> tuple[list[Task], int]:
        """Filter and paginate tasks using SQLAlchemy async queries."""
        stmt = select(Task).options(selectinload(Task.labels))
        count_stmt = select(func.count()).select_from(Task)

        status_filter: TaskStatus | None = kwargs.get("status")
        priority_filter: TaskPriority | None = kwargs.get("priority")
        project_id_filter: int | None = kwargs.get("project_id")
        assignee_id_filter: int | None = kwargs.get("assignee_id")
        search: str | None = kwargs.get("search")

        conditions = []
        if status_filter is not None:
            conditions.append(Task.status == status_filter)
        if priority_filter is not None:
            conditions.append(Task.priority == priority_filter)
        if project_id_filter is not None:
            conditions.append(Task.project_id == project_id_filter)
        if assignee_id_filter is not None:
            conditions.append(Task.assignee_id == assignee_id_filter)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar_one())

        stmt = (
            stmt.order_by(Task.created_at.desc(), Task.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total
