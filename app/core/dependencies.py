"""Dependency Injection definitions.

Uses typing.Annotated for all FastAPI dependencies per trainer guidelines:
"Dùng Annotated (DbSession, CurrentUser...) thay cho = Depends(...)".
"""

from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import messages
from app.core.config import Settings, get_settings
from app.core.constants import (
    BEARER_SCHEME,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
    MIN_STRING_LENGTH,
    TaskPriority,
    TaskStatus,
    TokenType,
    UserRole,
)
from app.core.database import DbSession
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.models.user import User
from app.repositories.comment import CommentRepository
from app.repositories.label import LabelRepository
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.user import RefreshTokenRepository, UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.base import PaginationParams
from app.schemas.task import TaskFilterParams
from app.services.auth import AuthService
from app.services.comment import CommentService
from app.services.label import LabelService
from app.services.project import ProjectService
from app.services.task import TaskService
from app.services.user import UserService
from app.services.workspace import WorkspaceService

# Enables Bearer Auth button ("Authorize") in Swagger UI / ReDoc
bearer_scheme = HTTPBearer(auto_error=False)


def get_task_repository(db: DbSession) -> TaskRepository:
    """Dependency provider for TaskRepository backed by AsyncSession."""
    return TaskRepository(db=db)


def get_user_repository(db: DbSession) -> UserRepository:
    """Dependency provider for UserRepository."""
    return UserRepository(db=db)


def get_refresh_token_repository(db: DbSession) -> RefreshTokenRepository:
    """Dependency provider for RefreshTokenRepository."""
    return RefreshTokenRepository(db=db)


def get_workspace_repository(db: DbSession) -> WorkspaceRepository:
    """Dependency provider for WorkspaceRepository."""
    return WorkspaceRepository(db=db)


def get_project_repository(db: DbSession) -> ProjectRepository:
    """Dependency provider for ProjectRepository."""
    return ProjectRepository(db=db)


def get_label_repository(db: DbSession) -> LabelRepository:
    """Dependency provider for LabelRepository."""
    return LabelRepository(db=db)


def get_comment_repository(db: DbSession) -> CommentRepository:
    """Dependency provider for CommentRepository."""
    return CommentRepository(db=db)


def get_workspace_service(
    repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> WorkspaceService:
    """Dependency provider for WorkspaceService."""
    return WorkspaceService(repository=repo, user_repository=user_repo)


def get_project_service(
    repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> ProjectService:
    """Dependency provider for ProjectService."""
    return ProjectService(repository=repo, workspace_repository=workspace_repo)


def get_task_service(
    repo: Annotated[TaskRepository, Depends(get_task_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> TaskService:
    """Dependency provider for TaskService with object-level RBAC repositories."""
    return TaskService(
        repository=repo,
        project_repository=project_repo,
        workspace_repository=workspace_repo,
        user_repository=user_repo,
    )


def get_label_service(
    repo: Annotated[LabelRepository, Depends(get_label_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> LabelService:
    """Dependency provider for LabelService."""
    return LabelService(
        repository=repo,
        project_repository=project_repo,
        task_repository=task_repo,
        workspace_repository=workspace_repo,
    )


def get_comment_service(
    repo: Annotated[CommentRepository, Depends(get_comment_repository)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> CommentService:
    """Dependency provider for CommentService."""
    return CommentService(
        repository=repo,
        task_repository=task_repo,
        project_repository=project_repo,
        workspace_repository=workspace_repo,
    )


def get_auth_service(
    db: DbSession,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_repo: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(db=db, user_repo=user_repo, refresh_repo=refresh_repo)


def get_user_service(
    db: DbSession,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_repo: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
) -> UserService:
    """Dependency provider for UserService."""
    return UserService(db=db, user_repo=user_repo, refresh_repo=refresh_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Centralized auth dependency: decode access token, load user, verify active."""
    if credentials is None or credentials.scheme.lower() != BEARER_SCHEME:
        raise UnauthorizedException(message=messages.TOKEN_INVALID)

    user_id, _ = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException(message=messages.TOKEN_INVALID)

    if not user.is_active:
        raise ForbiddenException(message=messages.INACTIVE_USER)

    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Restrict access exclusively to ADMIN users."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException(message=messages.PERMISSION_DENIED)
    return current_user


def get_pagination_params(
    page: Annotated[
        int, Query(ge=1, description="Page number", examples=[1])
    ] = DEFAULT_PAGE,
    page_size: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_PAGE_SIZE,
            description="Page size",
            examples=[10],
        ),
    ] = DEFAULT_PAGE_SIZE,
) -> PaginationParams:
    """Dependency extracting pagination parameters from query string."""
    return PaginationParams(page=page, page_size=page_size)


def get_task_filter_params(
    status: Annotated[
        TaskStatus | None, Query(description="Filter by task status")
    ] = None,
    priority: Annotated[
        TaskPriority | None, Query(description="Filter by task priority")
    ] = None,
    project_id_filter: Annotated[
        int | None, Query(alias="project_id", gt=0, description="Filter by project ID")
    ] = None,
    assignee_id: Annotated[
        int | None, Query(gt=0, description="Filter by assignee user ID")
    ] = None,
    search: Annotated[
        str | None,
        Query(
            min_length=MIN_STRING_LENGTH,
            max_length=MAX_SEARCH_LENGTH,
            description="Search term in title/description",
        ),
    ] = None,
) -> TaskFilterParams:
    """Dependency extracting task filters from query string."""
    return TaskFilterParams(
        status=status,
        priority=priority,
        project_id=project_id_filter,
        assignee_id=assignee_id,
        search=search,
    )


# Type aliases with Annotated dependencies for clean signatures in route handlers
SettingsDep = Annotated[Settings, Depends(get_settings)]
TaskRepositoryDep = Annotated[TaskRepository, Depends(get_task_repository)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
LabelServiceDep = Annotated[LabelService, Depends(get_label_service)]
CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
TaskFilterDep = Annotated[TaskFilterParams, Depends(get_task_filter_params)]
