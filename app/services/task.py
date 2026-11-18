"""Task business logic service layer with RBAC, caching, and notifications."""

import math

from fastapi import BackgroundTasks

from app.core import messages
from app.core.cache import CacheManager
from app.core.constants import TaskStatus, UserRole, WorkspaceRole
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.notifications import send_task_assigned_notification
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.task import (
    TaskCreate,
    TaskFilterParams,
    TaskResponse,
    TaskUpdate,
)


class TaskService:
    """Service handling task operations, RBAC, Redis caching, and notifications."""

    def __init__(
        self,
        repository: TaskRepository,
        project_repository: ProjectRepository,
        workspace_repository: WorkspaceRepository,
        user_repository: UserRepository,
        cache: CacheManager | None = None,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.workspace_repository = workspace_repository
        self.user_repository = user_repository
        self.cache = cache

    async def _verify_project_access(
        self,
        project_id: int,
        user: User,
        require_editor: bool = False,
    ) -> int:
        """Verify user is member of project's workspace, returning workspace_id."""
        project = await self.project_repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        if user.role == UserRole.ADMIN:
            return project.workspace_id

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

        return project.workspace_id

    async def _verify_assignee(
        self, workspace_id: int, assignee_id: int | None
    ) -> User | None:
        """Validate that assignee exists and belongs to workspace."""
        if assignee_id is None:
            return None

        target_user = await self.user_repository.get_by_id(assignee_id)
        if not target_user:
            raise NotFoundException(message=messages.USER_NOT_FOUND)

        membership = await self.workspace_repository.get_member(
            workspace_id, assignee_id
        )
        if not membership:
            raise BadRequestException(message=messages.ASSIGNEE_NOT_MEMBER)

        return target_user

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
        """Retrieve paginated and filtered tasks with Redis caching per project."""
        cache_key: str | None = None
        if filters.project_id is not None:
            await self._verify_project_access(
                project_id=filters.project_id,
                user=current_user,
                require_editor=False,
            )
            if self.cache is not None:
                cache_key = self.cache.build_project_tasks_key(
                    project_id=filters.project_id,
                    page=pagination.page,
                    page_size=pagination.page_size,
                    status=filters.status.value if filters.status else None,
                    priority=filters.priority.value if filters.priority else None,
                    assignee_id=filters.assignee_id,
                    search=filters.search,
                )
                cached_data = await self.cache.get_json(cache_key)
                if cached_data is not None:
                    return PaginatedResponse[TaskResponse].model_validate(cached_data)

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

        response = PaginatedResponse[TaskResponse](
            items=[TaskResponse.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )

        if cache_key is not None and self.cache is not None:
            await self.cache.set_json(cache_key, response.model_dump(mode="json"))

        return response

    async def create_task(
        self,
        task_in: TaskCreate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> TaskResponse:
        """Create a task, invalidate project cache, and notify assignee if set."""
        workspace_id = await self._verify_project_access(
            project_id=task_in.project_id,
            user=current_user,
            require_editor=True,
        )
        assignee = await self._verify_assignee(workspace_id, task_in.assignee_id)

        task = await self.repository.create(
            obj_in=task_in,
            created_by=current_user.id,
            status=TaskStatus.TODO,
        )

        if self.cache is not None:
            await self.cache.invalidate_project_tasks(task.project_id)

        if assignee is not None and background_tasks is not None:
            background_tasks.add_task(
                send_task_assigned_notification,
                recipient_email=assignee.email,
                recipient_name=assignee.full_name,
                task_id=task.id,
                task_title=task.title,
                project_id=task.project_id,
                assigned_by_email=current_user.email,
            )

        return TaskResponse.model_validate(task)

    async def update_task(
        self,
        task_id: int,
        task_in: TaskUpdate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> TaskResponse:
        """Partially update a task, invalidate cache, and notify new assignee."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        project = await self.project_repository.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
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

        previous_assignee_id = task.assignee_id
        new_assignee: User | None = None
        if task_in.assignee_id is not None:
            new_assignee = await self._verify_assignee(
                project.workspace_id, task_in.assignee_id
            )

        updated = await self.repository.update(task_id, obj_in=task_in)
        if not updated:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        if self.cache is not None:
            await self.cache.invalidate_project_tasks(updated.project_id)

        if (
            new_assignee is not None
            and new_assignee.id != previous_assignee_id
            and background_tasks is not None
        ):
            background_tasks.add_task(
                send_task_assigned_notification,
                recipient_email=new_assignee.email,
                recipient_name=new_assignee.full_name,
                task_id=updated.id,
                task_title=updated.title,
                project_id=updated.project_id,
                assigned_by_email=current_user.email,
            )

        return TaskResponse.model_validate(updated)

    async def delete_task(self, task_id: int, current_user: User) -> None:
        """Delete a task and invalidate cached project tasks."""
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

        if self.cache is not None:
            await self.cache.invalidate_project_tasks(task.project_id)
