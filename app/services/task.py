"""Task business logic service layer with workspace-scoped RBAC."""

import math

from app.core import messages
from app.core.constants import TaskStatus, UserRole, WorkspaceRole
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.task import (
    TaskCreate,
    TaskFilterParams,
    TaskResponse,
    TaskUpdate,
)


class TaskService:
    """Service handling task business operations and object-level permissions."""

    def __init__(
        self,
        repository: TaskRepository,
        project_repository: ProjectRepository,
        workspace_repository: WorkspaceRepository,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.workspace_repository = workspace_repository

    async def _verify_project_access(
        self,
        project_id: int,
        user: User,
        require_editor: bool = False,
    ) -> None:
        """Verify user is member of project's workspace with appropriate role."""
        if user.role == UserRole.ADMIN:
            return

        project = await self.project_repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        membership = await self.workspace_repository.get_member(
            project.workspace_id, user.id
        )
        if not membership:
            raise ForbiddenException(message=messages.NOT_WORKSPACE_MEMBER)

        if require_editor and membership.role not in (
            WorkspaceRole.OWNER,
            WorkspaceRole.EDITOR,
        ):
            raise ForbiddenException(message=messages.TASK_EDITOR_REQUIRED)

    async def get_task_by_id(self, task_id: int, current_user: User) -> TaskResponse:
        """Fetch a task by ID checking workspace membership."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        await self._verify_project_access(
            project_id=task.project_id,
            user=current_user,
            require_editor=False,
        )
        return TaskResponse.model_validate(task)

    async def list_tasks(
        self,
        pagination: PaginationParams,
        filters: TaskFilterParams,
        current_user: User,
    ) -> PaginatedResponse[TaskResponse]:
        """Retrieve paginated and filtered tasks with authorization."""
        if filters.project_id is not None:
            await self._verify_project_access(
                project_id=filters.project_id,
                user=current_user,
                require_editor=False,
            )

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
            items=[TaskResponse.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )

    async def create_task(
        self,
        task_in: TaskCreate,
        current_user: User,
    ) -> TaskResponse:
        """Create a new task under a project (requires OWNER or EDITOR in workspace)."""
        await self._verify_project_access(
            project_id=task_in.project_id,
            user=current_user,
            require_editor=True,
        )

        task = await self.repository.create(
            obj_in=task_in,
            created_by=current_user.id,
            status=TaskStatus.TODO,
        )
        return TaskResponse.model_validate(task)

    async def update_task(
        self,
        task_id: int,
        task_in: TaskUpdate,
        current_user: User,
    ) -> TaskResponse:
        """Partially update a task (requires OWNER, EDITOR, or assignee)."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            project = await self.project_repository.get_by_id(task.project_id)
            if not project:
                raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

            membership = await self.workspace_repository.get_member(
                project.workspace_id, current_user.id
            )
            if not membership:
                raise ForbiddenException(message=messages.NOT_WORKSPACE_MEMBER)

            is_assignee = task.assignee_id == current_user.id
            is_editor_or_owner = membership.role in (
                WorkspaceRole.OWNER,
                WorkspaceRole.EDITOR,
            )
            if not (is_assignee or is_editor_or_owner):
                raise ForbiddenException(message=messages.TASK_EDITOR_REQUIRED)

        updated = await self.repository.update(task_id, obj_in=task_in)
        if not updated:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
        return TaskResponse.model_validate(updated)

    async def delete_task(self, task_id: int, current_user: User) -> None:
        """Delete a task (requires OWNER or EDITOR in workspace)."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        await self._verify_project_access(
            project_id=task.project_id,
            user=current_user,
            require_editor=True,
        )

        deleted = await self.repository.delete(task_id)
        if not deleted:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
