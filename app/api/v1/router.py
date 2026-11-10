"""Main API v1 router consolidating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, tasks

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
