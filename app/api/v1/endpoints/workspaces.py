"""Workspace and workspace-scoped resource endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.core.constants import ProjectStatus
from app.core.dependencies import (
    CurrentUser,
    PaginationDep,
    ProjectServiceDep,
    WorkspaceServiceDep,
)
from app.core.openapi import build_error_responses
from app.schemas.base import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)

router = APIRouter()


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Create workspace",
    description="Creates a new workspace with the authenticated user as OWNER.",
)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Create workspace endpoint."""
    return await service.create_workspace(
        workspace_in=workspace_in, current_user=current_user
    )


@router.get(
    "",
    response_model=PaginatedResponse[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(status.HTTP_401_UNAUTHORIZED),
    summary="List workspaces",
    description="Lists workspaces accessible to the authenticated user.",
)
async def list_workspaces(
    current_user: CurrentUser,
    pagination: PaginationDep,
    service: WorkspaceServiceDep,
) -> PaginatedResponse[WorkspaceResponse]:
    """List workspaces endpoint."""
    return await service.list_workspaces(
        current_user=current_user, pagination=pagination
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Get workspace details",
    description="Retrieves workspace details if user is a member or admin.",
)
async def get_workspace(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Get workspace details endpoint."""
    return await service.get_workspace_by_id(
        workspace_id=workspace_id, current_user=current_user
    )


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Update workspace",
    description="Updates workspace name (OWNER or ADMIN only).",
)
async def update_workspace(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    workspace_in: WorkspaceUpdate,
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Update workspace endpoint."""
    return await service.update_workspace(
        workspace_id=workspace_id,
        workspace_in=workspace_in,
        current_user=current_user,
    )


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Delete workspace",
    description="Deletes a workspace and its resources (OWNER or ADMIN only).",
)
async def delete_workspace(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> None:
    """Delete workspace endpoint."""
    await service.delete_workspace(workspace_id=workspace_id, current_user=current_user)


# ==============================================================================
# Workspace Members
# ==============================================================================
@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Invite/Add workspace member",
    description="Adds a user to the workspace with a role (OWNER or ADMIN only).",
)
async def add_workspace_member(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    member_in: WorkspaceMemberCreate,
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    """Add member endpoint."""
    return await service.add_member(
        workspace_id=workspace_id,
        member_in=member_in,
        current_user=current_user,
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="List workspace members",
    description="Lists all members of a workspace (members or ADMIN only).",
)
async def list_workspace_members(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> list[WorkspaceMemberResponse]:
    """List members endpoint."""
    return await service.list_members(
        workspace_id=workspace_id, current_user=current_user
    )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Remove workspace member",
    description="Removes a member from the workspace (OWNER/ADMIN or self-leave).",
)
async def remove_workspace_member(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    user_id: Annotated[int, Path(gt=0, description="User ID to remove")],
    current_user: CurrentUser,
    service: WorkspaceServiceDep,
) -> None:
    """Remove member endpoint."""
    await service.remove_member(
        workspace_id=workspace_id,
        target_user_id=user_id,
        current_user=current_user,
    )


# ==============================================================================
# Projects Scoped to Workspace
# ==============================================================================
@router.post(
    "/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Create project in workspace",
    description="Creates a project within a workspace (OWNER/EDITOR or ADMIN only).",
)
async def create_project_in_workspace(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    project_in: ProjectCreate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Create project endpoint."""
    return await service.create_project(
        workspace_id=workspace_id,
        project_in=project_in,
        current_user=current_user,
    )


@router.get(
    "/{workspace_id}/projects",
    response_model=PaginatedResponse[ProjectResponse],
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="List projects in workspace",
    description="Lists projects within a workspace with optional status filter.",
)
async def list_projects_in_workspace(
    workspace_id: Annotated[int, Path(gt=0, description="Workspace ID")],
    current_user: CurrentUser,
    pagination: PaginationDep,
    service: ProjectServiceDep,
    status_filter: Annotated[
        ProjectStatus | None,
        Query(alias="status", description="Filter by status (ACTIVE, ARCHIVED)"),
    ] = None,
) -> PaginatedResponse[ProjectResponse]:
    """List projects endpoint."""
    return await service.list_projects(
        workspace_id=workspace_id,
        current_user=current_user,
        pagination=pagination,
        status=status_filter,
    )
