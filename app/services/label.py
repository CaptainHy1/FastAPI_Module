"""Label business logic service layer."""

from app.core import messages
from app.core.constants import UserRole, WorkspaceRole
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.models.user import User
from app.repositories.label import LabelRepository
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.label import LabelCreate, LabelResponse
from app.schemas.task import TaskResponse


class LabelService:
    """Service handling project-scoped labels and task assignments."""

    def __init__(
        self,
        repository: LabelRepository,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        workspace_repository: WorkspaceRepository,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.workspace_repository = workspace_repository

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
            raise ForbiddenException(message=messages.PROJECT_EDITOR_REQUIRED)

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
        self, project_id: int, current_user: User
    ) -> list[LabelResponse]:
        """List all labels in a project (workspace members or ADMIN)."""
        await self._verify_project_access(
            project_id=project_id, user=current_user, require_editor=False
        )
        labels = await self.repository.list_by_project(project_id)
        return [LabelResponse.model_validate(item) for item in labels]

    async def delete_label(self, label_id: int, current_user: User) -> None:
        """Delete a label (OWNER/EDITOR or ADMIN only)."""
        label = await self.repository.get_by_id(label_id)
        if not label:
            raise NotFoundException(message=messages.LABEL_NOT_FOUND)

        await self._verify_project_access(
            project_id=label.project_id, user=current_user, require_editor=True
        )
        await self.repository.delete(label_id)

    async def attach_label_to_task(
        self, task_id: int, label_id: int, current_user: User
    ) -> TaskResponse:
        """Attach label to task, ensuring same project and proper permissions."""
        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        label = await self.repository.get_by_id(label_id)
        if not label:
            raise NotFoundException(message=messages.LABEL_NOT_FOUND)

        # Enforce that label belongs to the same project as the task
        if label.project_id != task.project_id:
            raise BadRequestException(message=messages.LABEL_PROJECT_MISMATCH)

        # Check permission: OWNER/EDITOR or task assignee
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

        await self.repository.attach_to_task(task, label)
        updated_task = await self.task_repository.get_by_id(task_id)
        return TaskResponse.model_validate(updated_task)

    async def remove_label_from_task(
        self, task_id: int, label_id: int, current_user: User
    ) -> TaskResponse:
        """Remove a label from a task."""
        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        label = await self.repository.get_by_id(label_id)
        if not label:
            raise NotFoundException(message=messages.LABEL_NOT_FOUND)

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

        await self.repository.remove_from_task(task, label)
        updated_task = await self.task_repository.get_by_id(task_id)
        return TaskResponse.model_validate(updated_task)
