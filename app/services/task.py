"""Task business logic service layer."""

import math

from app.core import messages
from app.core.exceptions import NotFoundException
from app.repositories.task import TaskRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.task import (
    TaskCreate,
    TaskFilterParams,
    TaskResponse,
    TaskUpdate,
)


class TaskService:
    """Service handling task business operations."""

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def get_task_by_id(self, task_id: int) -> TaskResponse:
        """Fetch a task by ID or raise NotFoundException."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
        return task

    async def list_tasks(
        self,
        pagination: PaginationParams,
        filters: TaskFilterParams,
    ) -> PaginatedResponse[TaskResponse]:
        """Retrieve paginated and filtered tasks."""
        items, total = await self.repository.list_items(
            skip=pagination.skip,
            limit=pagination.limit,
            status=filters.status,
            priority=filters.priority,
            project_id=filters.project_id,
            assignee_id=filters.assignee_id,
            search=filters.search,
        )

        total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0

        return PaginatedResponse[TaskResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )

    async def create_task(
        self, task_in: TaskCreate, creator_id: int = 1
    ) -> TaskResponse:
        """Create a new task under a project."""
        return await self.repository.create(obj_in=task_in, created_by=creator_id)

    async def update_task(self, task_id: int, task_in: TaskUpdate) -> TaskResponse:
        """Partially update a task or raise NotFoundException."""
        task = await self.repository.update(task_id, obj_in=task_in)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
        return task

    async def delete_task(self, task_id: int) -> None:
        """Delete a task or raise NotFoundException."""
        deleted = await self.repository.delete(task_id)
        if not deleted:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
