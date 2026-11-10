"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter, status

from app.core import messages
from app.core.dependencies import SettingsDep

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns application health status, version, and running environment.",
)
async def health_check(settings: SettingsDep) -> dict[str, Any]:
    """Return system health details."""
    return {
        "status": "healthy",
        "message": messages.HEALTH_CHECK_OK,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
