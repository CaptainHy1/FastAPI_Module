"""Main API v1 router consolidating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, projects, tasks, users, workspaces

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(
    workspaces.router, prefix="/workspaces", tags=["Workspaces"]
)
api_v1_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_v1_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
