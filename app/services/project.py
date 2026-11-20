"""Project business logic service layer with workspace-scoped RBAC."""

import math

from app.core import messages
from app.core.constants import ProjectStatus, WorkspaceRole
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.workspace import require_workspace_role


class ProjectService:
    """Service handling project management and object-level permissions."""

    def __init__(
        self,
        repository: ProjectRepository,
        workspace_repository: WorkspaceRepository,
    ) -> None:
        self.repository = repository
        self.workspace_repository = workspace_repository

    async def create_project(
        self,
        workspace_id: int,
        project_in: ProjectCreate,
        current_user: User,
    ) -> ProjectResponse:
        """Create a new project in a workspace (OWNER/EDITOR or ADMIN only)."""
        workspace = await self.workspace_repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        await require_workspace_role(
            self.workspace_repository,
            workspace_id,
            current_user,
            {WorkspaceRole.OWNER, WorkspaceRole.EDITOR},
            forbidden_message=messages.PROJECT_EDITOR_REQUIRED,
        )

        project = await self.repository.create(
            obj_in=project_in,
            workspace_id=workspace_id,
            status=ProjectStatus.ACTIVE,
        )
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self,
        workspace_id: int,
        current_user: User,
        pagination: PaginationParams,
        status: ProjectStatus | None = None,
    ) -> PaginatedResponse[ProjectResponse]:
        """List projects in a workspace (members or ADMIN)."""
        workspace = await self.workspace_repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        await require_workspace_role(
            self.workspace_repository,
            workspace_id,
            current_user,
        )

        items, total = await self.repository.list_by_workspace(
            workspace_id=workspace_id,
            status=status,
            skip=pagination.skip,
            limit=pagination.page_size,
        )
        total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0

        return PaginatedResponse[ProjectResponse](
            items=[ProjectResponse.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )

    async def get_project_by_id(
        self, project_id: int, current_user: User
    ) -> ProjectResponse:
        """Fetch project details checking workspace membership."""
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        await require_workspace_role(
            self.workspace_repository,
            project.workspace_id,
            current_user,
        )

        return ProjectResponse.model_validate(project)

    async def update_project(
        self,
        project_id: int,
        project_in: ProjectUpdate,
        current_user: User,
    ) -> ProjectResponse:
        """Update project details (OWNER/EDITOR or ADMIN only)."""
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        await require_workspace_role(
            self.workspace_repository,
            project.workspace_id,
            current_user,
            {WorkspaceRole.OWNER, WorkspaceRole.EDITOR},
            forbidden_message=messages.PROJECT_EDITOR_REQUIRED,
        )

        updated = await self.repository.update(project_id, obj_in=project_in)
        if not updated:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)
        return ProjectResponse.model_validate(updated)

    async def delete_project(self, project_id: int, current_user: User) -> None:
        """Delete a project (Workspace OWNER or ADMIN only)."""
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        await require_workspace_role(
            self.workspace_repository,
            project.workspace_id,
            current_user,
            {WorkspaceRole.OWNER},
        )

        await self.repository.delete(project_id)
