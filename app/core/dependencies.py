"""Dependency Injection definitions.

Uses typing.Annotated for all FastAPI dependencies per trainer guidelines:
"Dùng Annotated (DbSession, CurrentUser...) thay cho = Depends(...)".
"""

from typing import Annotated

from fastapi import Depends, Query

from app.core.config import Settings, get_settings
from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, TaskPriority, TaskStatus
from app.core.database import DbSession
from app.repositories.task import TaskRepository
from app.schemas.base import PaginationParams
from app.schemas.task import TaskFilterParams
from app.services.task import TaskService


def get_task_repository(db: DbSession) -> TaskRepository:
    """Dependency provider for TaskRepository backed by AsyncSession."""
    return TaskRepository(db=db)


def get_task_service(
    repo: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    """Dependency provider for TaskService."""
    return TaskService(repository=repo)


def get_pagination_params(
    page: Annotated[
        int, Query(ge=1, description="Page number", examples=[1])
    ] = DEFAULT_PAGE,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Page size", examples=[10])
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
    project_id: Annotated[
        int | None, Query(gt=0, description="Filter by project ID")
    ] = None,
    assignee_id: Annotated[
        int | None, Query(gt=0, description="Filter by assignee user ID")
    ] = None,
    search: Annotated[
        str | None,
        Query(
            min_length=1, max_length=100, description="Search term in title/description"
        ),
    ] = None,
) -> TaskFilterParams:
    """Dependency extracting task filters from query string."""
    return TaskFilterParams(
        status=status,
        priority=priority,
        project_id=project_id,
        assignee_id=assignee_id,
        search=search,
    )


# Type aliases with Annotated dependencies for clean signatures in route handlers
SettingsDep = Annotated[Settings, Depends(get_settings)]
TaskRepositoryDep = Annotated[TaskRepository, Depends(get_task_repository)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
TaskFilterDep = Annotated[TaskFilterParams, Depends(get_task_filter_params)]
