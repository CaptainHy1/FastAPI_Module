"""Workspace business logic service layer with fine-grained RBAC."""

import math

from app.core import messages
from app.core.constants import UserRole, WorkspaceRole
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.user import User
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginatedResponse, PaginationParams
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)


class WorkspaceService:
    """Service handling workspace CRUD, membership, and RBAC authorization."""

    def __init__(
        self,
        repository: WorkspaceRepository,
        user_repository: UserRepository,
    ) -> None:
        self.repository = repository
        self.user_repository = user_repository

    async def create_workspace(
        self, workspace_in: WorkspaceCreate, current_user: User
    ) -> WorkspaceResponse:
        """Create a workspace and record current user as its OWNER."""
        workspace = await self.repository.create_workspace_with_owner(
            name=workspace_in.name,
            owner_id=current_user.id,
        )
        return WorkspaceResponse.model_validate(workspace)

    async def list_workspaces(
        self,
        current_user: User,
        pagination: PaginationParams,
    ) -> PaginatedResponse[WorkspaceResponse]:
        """List workspaces accessible to current user."""
        is_admin = current_user.role == UserRole.ADMIN
        items, total = await self.repository.list_user_workspaces(
            user_id=current_user.id,
            skip=pagination.skip,
            limit=pagination.page_size,
            is_admin=is_admin,
        )
        total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0

        return PaginatedResponse[WorkspaceResponse](
            items=[WorkspaceResponse.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )

    async def get_workspace_by_id(
        self, workspace_id: int, current_user: User
    ) -> WorkspaceResponse:
        """Fetch workspace ensuring user is member or admin."""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            membership = await self.repository.get_member(workspace_id, current_user.id)
            if not membership:
                raise ForbiddenException(message=messages.NOT_WORKSPACE_MEMBER)

        return WorkspaceResponse.model_validate(workspace)

    async def update_workspace(
        self,
        workspace_id: int,
        workspace_in: WorkspaceUpdate,
        current_user: User,
    ) -> WorkspaceResponse:
        """Update workspace name (OWNER or ADMIN only)."""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            membership = await self.repository.get_member(workspace_id, current_user.id)
            if not membership or membership.role != WorkspaceRole.OWNER:
                raise ForbiddenException(message=messages.WORKSPACE_OWNER_REQUIRED)

        updated = await self.repository.update(workspace_id, obj_in=workspace_in)
        if not updated:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)
        return WorkspaceResponse.model_validate(updated)

    async def delete_workspace(self, workspace_id: int, current_user: User) -> None:
        """Delete workspace (OWNER or ADMIN only)."""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            membership = await self.repository.get_member(workspace_id, current_user.id)
            if not membership or membership.role != WorkspaceRole.OWNER:
                raise ForbiddenException(message=messages.WORKSPACE_OWNER_REQUIRED)

        await self.repository.delete(workspace_id)

    async def add_member(
        self,
        workspace_id: int,
        member_in: WorkspaceMemberCreate,
        current_user: User,
    ) -> WorkspaceMemberResponse:
        """Add or invite a member to workspace (OWNER or ADMIN only)."""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            membership = await self.repository.get_member(workspace_id, current_user.id)
            if not membership or membership.role != WorkspaceRole.OWNER:
                raise ForbiddenException(message=messages.WORKSPACE_OWNER_REQUIRED)

        # Validate target user exists
        target_user = await self.user_repository.get_by_id(member_in.user_id)
        if not target_user:
            raise NotFoundException(message=messages.USER_NOT_FOUND)

        member = await self.repository.add_member(
            workspace_id=workspace_id,
            user_id=member_in.user_id,
            role=member_in.role,
        )

        return WorkspaceMemberResponse(
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            role=member.role,
            email=target_user.email,
            full_name=target_user.full_name,
        )

    async def list_members(
        self, workspace_id: int, current_user: User
    ) -> list[WorkspaceMemberResponse]:
        """List all members in a workspace (Members or ADMIN)."""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        if current_user.role != UserRole.ADMIN:
            membership = await self.repository.get_member(workspace_id, current_user.id)
            if not membership:
                raise ForbiddenException(message=messages.NOT_WORKSPACE_MEMBER)

        members = await self.repository.list_members(workspace_id)
        return [
            WorkspaceMemberResponse(
                workspace_id=m.workspace_id,
                user_id=m.user_id,
                role=m.role,
                email=m.user.email if m.user else None,
                full_name=m.user.full_name if m.user else None,
            )
            for m in members
        ]

    async def remove_member(
        self,
        workspace_id: int,
        target_user_id: int,
        current_user: User,
    ) -> None:
        """Remove a member (OWNER/ADMIN or self-leave). Owner cannot be removed."""
        workspace = await self.repository.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(message=messages.WORKSPACE_NOT_FOUND)

        if target_user_id == workspace.owner_id:
            raise ForbiddenException(message=messages.CANNOT_REMOVE_WORKSPACE_OWNER)

        # Caller must be OWNER/ADMIN or removing self
        if current_user.id != target_user_id and current_user.role != UserRole.ADMIN:
            caller_membership = await self.repository.get_member(
                workspace_id, current_user.id
            )
            if not caller_membership or caller_membership.role != WorkspaceRole.OWNER:
                raise ForbiddenException(message=messages.WORKSPACE_OWNER_REQUIRED)

        existing_member = await self.repository.get_member(workspace_id, target_user_id)
        if not existing_member:
            raise NotFoundException(message=messages.MEMBER_NOT_FOUND)

        await self.repository.remove_member(workspace_id, target_user_id)
