"""Task repository implementation.

In Session 1 (Core Setup & Architecture), this provides an in-memory async
data-access implementation conforming to BaseRepository[T, CreateSchema, UpdateSchema].
In Session 2, this will be extended/swapped with SQLAlchemy 2.x async repository.
"""

from datetime import UTC, datetime
from typing import Any

from app.core.constants import TaskPriority, TaskStatus
from app.repositories.base import BaseRepository
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate


class TaskRepository(BaseRepository[TaskResponse, TaskCreate, TaskUpdate]):
    """Repository managing Task entities with async CRUD capabilities."""

    def __init__(self) -> None:
        self._storage: dict[int, TaskResponse] = {}
        self._current_id: int = 0

    async def get_by_id(self, id_: int) -> TaskResponse | None:
        """Fetch task by ID."""
        return self._storage.get(id_)

    async def list_items(
        self,
        skip: int = 0,
        limit: int = 10,
        **kwargs: Any,
    ) -> tuple[list[TaskResponse], int]:
        """Filter and paginate tasks."""
        items = list(self._storage.values())

        status_filter: TaskStatus | None = kwargs.get("status")
        priority_filter: TaskPriority | None = kwargs.get("priority")
        project_id_filter: int | None = kwargs.get("project_id")
        assignee_id_filter: int | None = kwargs.get("assignee_id")
        search: str | None = kwargs.get("search")

        if status_filter is not None:
            items = [t for t in items if t.status == status_filter]

        if priority_filter is not None:
            items = [t for t in items if t.priority == priority_filter]

        if project_id_filter is not None:
            items = [t for t in items if t.project_id == project_id_filter]

        if assignee_id_filter is not None:
            items = [t for t in items if t.assignee_id == assignee_id_filter]

        if search:
            search_lower = search.lower()
            items = [
                t
                for t in items
                if search_lower in t.title.lower()
                or (t.description and search_lower in t.description.lower())
            ]

        total = len(items)
        paginated_items = items[skip : skip + limit]
        return paginated_items, total

    async def create(
        self,
        obj_in: TaskCreate,
        **kwargs: Any,
    ) -> TaskResponse:
        """Persist a new task."""
        created_by: int = int(kwargs.get("created_by", 1))
        self._current_id += 1
        now = datetime.now(UTC)

        task = TaskResponse(
            id=self._current_id,
            title=obj_in.title,
            description=obj_in.description,
            status=obj_in.status,
            priority=obj_in.priority,
            due_date=obj_in.due_date,
            assignee_id=obj_in.assignee_id,
            project_id=obj_in.project_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._storage[self._current_id] = task
        return task

    async def update(
        self,
        id_: int,
        obj_in: TaskUpdate,
        **kwargs: Any,
    ) -> TaskResponse | None:
        """Partially update an existing task."""
        existing = self._storage.get(id_)
        if not existing:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        if not update_data:
            return existing

        task_dict = existing.model_dump()
        task_dict.update(update_data)
        task_dict["updated_at"] = datetime.now(UTC)

        updated_task = TaskResponse(**task_dict)
        self._storage[id_] = updated_task
        return updated_task

    async def delete(self, id_: int) -> bool:
        """Delete task by ID."""
        if id_ in self._storage:
            del self._storage[id_]
            return True
        return False
