"""Task business logic service layer with RBAC and versioned Redis caching."""

import logging

from fastapi import BackgroundTasks
from pydantic import ValidationError

from app.core import messages
from app.core.cache import CacheManager
from app.core.constants import (
    TaskStatus,
    UserRole,
    WorkspaceRole,
)
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnprocessableEntityException,
)
from app.core.notifications import send_task_assigned_notification
from app.models.project import Project
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.task import TaskCreate, TaskFilterParams, TaskResponse, TaskUpdate
from app.services.workspace import require_workspace_role

logger = logging.getLogger("taskhub.services.task")


class TaskService:
    """Service handling task CRUD, assignment notifications, and versioned caching."""

    def __init__(
        self,
        repository: TaskRepository,
        project_repository: ProjectRepository,
        workspace_repository: WorkspaceRepository,
        user_repository: UserRepository,
        cache: CacheManager,
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
    ) -> Project:
        """Verify project existence and workspace authorization."""
        project = await self.project_repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        allowed_roles = (
            {WorkspaceRole.OWNER, WorkspaceRole.EDITOR} if require_editor else None
        )
        forbidden_message = (
            messages.PROJECT_EDITOR_REQUIRED
            if require_editor
            else messages.NOT_WORKSPACE_MEMBER
        )
        await require_workspace_role(
            self.workspace_repository,
            project.workspace_id,
            user,
            allowed_roles=allowed_roles,
            forbidden_message=forbidden_message,
        )
        return project

    async def _verify_assignee(self, workspace_id: int, assignee_id: int) -> User:
        """Verify assignee is an active user and belongs to the project's workspace."""
        assignee = await self.user_repository.get_by_id(assignee_id)
        if not assignee:
            raise NotFoundException(message=messages.USER_NOT_FOUND)

        membership = await self.workspace_repository.get_member(
            workspace_id, assignee_id
        )
        if membership is None:
            raise UnprocessableEntityException(
                message=messages.ASSIGNEE_NOT_WORKSPACE_MEMBER
            )
        return assignee

    def _notify_assignee(
        self,
        background_tasks: BackgroundTasks,
        recipient_id: int,
        task_id: int,
        project_id: int,
        assigned_by_id: int,
    ) -> None:
        """Schedule background notification without leaking sensitive PII."""
        background_tasks.add_task(
            send_task_assigned_notification,
            recipient_id=recipient_id,
            task_id=task_id,
            project_id=project_id,
            assigned_by_id=assigned_by_id,
        )

    async def get_task_by_id(self, task_id: int, current_user: User) -> TaskResponse:
        """Retrieve task by ID with RBAC check."""
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
            ver = await self.cache.get_project_version(filters.project_id)
            status_arg = (
                [s.value for s in filters.status]
                if isinstance(filters.status, list)
                else (filters.status.value if filters.status else None)
            )
            priority_arg = (
                [p.value for p in filters.priority]
                if isinstance(filters.priority, list)
                else (filters.priority.value if filters.priority else None)
            )
            cache_key = self.cache.build_project_tasks_key(
                project_id=filters.project_id,
                version=ver,
                page=pagination.page,
                page_size=pagination.page_size,
                status=status_arg,
                priority=priority_arg,
                assignee_id=filters.assignee_id,
                search=filters.search,
            )
            cached_data = await self.cache.get_json(cache_key)
            if cached_data is not None:
                try:
                    return PaginatedResponse[TaskResponse].model_validate(cached_data)
                except ValidationError as exc:
                    logger.warning(
                        "Schema mismatch in cache '%s': %s. Treating as miss.",
                        cache_key,
                        exc,
                    )

        # Non-admin users are strictly scoped to their workspaces (BOLA mitigation)
        member_user_id = (
            current_user.id if current_user.role != UserRole.ADMIN else None
        )

        items, total = await self.repository.list_items(
            skip=pagination.skip,
            limit=pagination.limit,
            status=filters.status,
            priority=filters.priority,
            project_id=filters.project_id,
            assignee_id=filters.assignee_id,
            search=filters.search,
            member_user_id=member_user_id,
        )

        response = PaginatedResponse[TaskResponse].create(
            items=[TaskResponse.model_validate(item) for item in items],
            total=total,
            pagination=pagination,
        )

        if cache_key is not None:
            await self.cache.set_json(cache_key, response.model_dump(mode="json"))

        return response

    async def create_task(
        self,
        task_in: TaskCreate,
        current_user: User,
        background_tasks: BackgroundTasks,
    ) -> TaskResponse:
        """Create a task, invalidate project cache, and notify assignee if set."""
        project = await self._verify_project_access(
            project_id=task_in.project_id,
            user=current_user,
            require_editor=True,
        )
        if task_in.assignee_id is not None:
            await self._verify_assignee(project.workspace_id, task_in.assignee_id)

        task = await self.repository.create(
            obj_in=task_in,
            created_by=current_user.id,
            status=TaskStatus.TODO,
        )

        await self.cache.invalidate_project_tasks(task.project_id)

        if task.assignee_id is not None:
            self._notify_assignee(
                background_tasks,
                recipient_id=task.assignee_id,
                task_id=task.id,
                project_id=task.project_id,
                assigned_by_id=current_user.id,
            )

        return TaskResponse.model_validate(task)

    async def update_task(
        self,
        task_id: int,
        task_in: TaskUpdate,
        current_user: User,
        background_tasks: BackgroundTasks,
    ) -> TaskResponse:
        """Partially update task, bump cache version, and notify on reassignment."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        project = await self.project_repository.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            membership = await require_workspace_role(
                self.workspace_repository,
                project.workspace_id,
                current_user,
            )
            is_assignee = task.assignee_id == current_user.id
            is_editor_or_owner = membership is not None and membership.role in (
                WorkspaceRole.OWNER,
                WorkspaceRole.EDITOR,
            )
            if not (is_assignee or is_editor_or_owner):
                raise ForbiddenException(message=messages.TASK_EDITOR_REQUIRED)

            # Assignee who is only a VIEWER can only update 'status'
            if is_assignee and not is_editor_or_owner:
                update_fields = task_in.model_dump(exclude_unset=True)
                if any(field != "status" for field in update_fields):
                    raise ForbiddenException(message=messages.ASSIGNEE_STATUS_ONLY)

        previous_assignee_id = task.assignee_id
        update_data = task_in.model_dump(exclude_unset=True)
        if "assignee_id" in update_data and task_in.assignee_id is not None:
            await self._verify_assignee(project.workspace_id, task_in.assignee_id)

        updated = await self.repository.update(task_id, obj_in=task_in)
        if not updated:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        await self.cache.invalidate_project_tasks(updated.project_id)

        if (
            updated.assignee_id is not None
            and updated.assignee_id != previous_assignee_id
        ):
            self._notify_assignee(
                background_tasks,
                recipient_id=updated.assignee_id,
                task_id=updated.id,
                project_id=updated.project_id,
                assigned_by_id=current_user.id,
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
        await self.repository.delete(task_id)
        await self.cache.invalidate_project_tasks(task.project_id)
