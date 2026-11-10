"""Global exception handlers registered on the FastAPI application."""

import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core import messages
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions and format uniform JSON response."""
    content: dict[str, Any] = {
        "error": {
            "code": exc.status_code,
            "message": exc.message,
        }
    }
    if exc.extra:
        content["error"]["details"] = exc.extra

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format request validation errors into a clean, uniform error response."""
    errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = " -> ".join(str(loc_item) for loc_item in err.get("loc", []))
        errors.append(
            {
                "field": loc,
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )

    content: dict[str, Any] = {
        "error": {
            "code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": messages.VALIDATION_FAILED,
            "details": errors,
        }
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=content,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled errors, log the exception, and return a safe 500 error."""
    logger.exception("Unhandled server exception at %s: %s", request.url.path, exc)
    content: dict[str, Any] = {
        "error": {
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": messages.INTERNAL_SERVER_ERROR,
        }
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )
