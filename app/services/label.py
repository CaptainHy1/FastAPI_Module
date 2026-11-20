"""Label business logic service layer."""

import math

from app.core import messages
from app.core.cache import CacheManager
from app.core.constants import WorkspaceRole
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.models.user import User
from app.repositories.label import LabelRepository
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.label import LabelCreate, LabelResponse
from app.schemas.task import TaskResponse
from app.services.workspace import require_workspace_role


class LabelService:
    """Service handling project-scoped labels and task assignments."""

    def __init__(
        self,
        repository: LabelRepository,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        workspace_repository: WorkspaceRepository,
        cache: CacheManager,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.workspace_repository = workspace_repository
        self.cache = cache

    async def _verify_project_access(
        self,
        project_id: int,
        user: User,
        require_editor: bool = False,
    ) -> int:
        """Verify project access and return workspace_id."""
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
        return project.workspace_id

    async def create_label(
        self,
        project_id: int,
        label_in: LabelCreate,
        current_user: User,
    ) -> LabelResponse:
        """Create a new label in project (OWNER/EDITOR or ADMIN only)."""
        await self._verify_project_access(
            project_id=project_id, user=current_user, require_editor=True
        )
        label = await self.repository.create_label(
            project_id=project_id,
            name=label_in.name,
            color=label_in.color,
        )
        return LabelResponse.model_validate(label)

    async def list_labels(
        self,
        project_id: int,
        current_user: User,
        pagination: PaginationParams,
    ) -> PaginatedResponse[LabelResponse]:
        """List all labels in a project (workspace members or ADMIN)."""
        await self._verify_project_access(
            project_id=project_id, user=current_user, require_editor=False
        )
        items, total = await self.repository.list_by_project(
            project_id=project_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )
        total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0
        return PaginatedResponse(
            items=[LabelResponse.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )

    async def delete_label(self, label_id: int, current_user: User) -> None:
        """Delete a label (OWNER/EDITOR or ADMIN only)."""
        label = await self.repository.get_by_id(label_id)
        if not label:
            raise NotFoundException(message=messages.LABEL_NOT_FOUND)

        await self._verify_project_access(
            project_id=label.project_id, user=current_user, require_editor=True
        )
        await self.repository.delete(label_id)
        await self.cache.invalidate_project_tasks(label.project_id)

    async def attach_label_to_task(
        self, task_id: int, label_id: int, current_user: User
    ) -> TaskResponse:
        """Attach label to task, ensuring same project and proper permissions."""
        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        project = await self.project_repository.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        # OWNER/EDITOR or ADMIN only (VIEWER assignees cannot attach labels)
        await require_workspace_role(
            self.workspace_repository,
            project.workspace_id,
            current_user,
            allowed_roles={WorkspaceRole.OWNER, WorkspaceRole.EDITOR},
            forbidden_message=messages.TASK_EDITOR_REQUIRED,
        )

        label = await self.repository.get_by_id(label_id)
        if not label:
            raise NotFoundException(message=messages.LABEL_NOT_FOUND)

        # Enforce that label belongs to the same project as the task
        if label.project_id != task.project_id:
            raise BadRequestException(message=messages.LABEL_PROJECT_MISMATCH)

        project_id = task.project_id
        await self.repository.attach_to_task(task_id=task.id, label_id=label.id)
        await self.cache.invalidate_project_tasks(project_id)
        updated_task = await self.task_repository.get_by_id(task_id)
        if not updated_task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
        return TaskResponse.model_validate(updated_task)

    async def remove_label_from_task(
        self, task_id: int, label_id: int, current_user: User
    ) -> TaskResponse:
        """Remove a label from a task."""
        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        project = await self.project_repository.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        # Check permission: OWNER/EDITOR or ADMIN only
        await require_workspace_role(
            self.workspace_repository,
            project.workspace_id,
            current_user,
            allowed_roles={WorkspaceRole.OWNER, WorkspaceRole.EDITOR},
            forbidden_message=messages.TASK_EDITOR_REQUIRED,
        )

        label = await self.repository.get_by_id(label_id)
        if not label:
            raise NotFoundException(message=messages.LABEL_NOT_FOUND)

        project_id = task.project_id
        await self.repository.remove_from_task(task_id=task.id, label_id=label.id)
        await self.cache.invalidate_project_tasks(project_id)
        updated_task = await self.task_repository.get_by_id(task_id)
        if not updated_task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)
        return TaskResponse.model_validate(updated_task)
