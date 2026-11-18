"""Main API v1 router consolidating all sub-routers with OpenAPI error docs."""

from fastapi import APIRouter, status

from app.api.v1.endpoints import (
    auth,
    comments,
    health,
    labels,
    projects,
    tasks,
    users,
    workspaces,
)
from app.core.openapi import build_error_responses

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"],
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
api_v1_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
api_v1_router.include_router(
    workspaces.router,
    prefix="/workspaces",
    tags=["Workspaces"],
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
api_v1_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"],
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
api_v1_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["Tasks"],
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
api_v1_router.include_router(
    labels.router,
    prefix="/labels",
    tags=["Labels"],
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
api_v1_router.include_router(
    comments.router,
    prefix="/comments",
    tags=["Comments"],
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
