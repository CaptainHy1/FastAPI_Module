"""OpenAPI metadata, tag descriptions, and reusable error response definitions."""

from typing import Any

from fastapi import status

from app.core import messages
from app.schemas.base import ErrorResponse

OPENAPI_DESCRIPTION: str = """
**TaskHub API** is a multi-tenant Task Management REST API built with **FastAPI**,
**SQLAlchemy 2.x Async**, **PostgreSQL 18**, and **Redis 7**.

### Authentication
Most endpoints require a JWT **Bearer Access Token** in the `Authorization` header:
1. Register via `POST /api/v1/auth/register` or login via `POST /api/v1/auth/login`.
2. Click the **Authorize** button above and paste your `access_token`.
3. Rotate expiring tokens with `POST /api/v1/auth/refresh`.

### Role-Based Access Control (RBAC)
- **System Roles**: `ADMIN`, `MEMBER`
- **Workspace Roles**: `OWNER`, `EDITOR`, `VIEWER`

### Standard Error Envelope
All domain and validation errors return a consistent JSON structure:
```json
{
  "error": {
    "code": 403,
    "message": "You do not have permission to perform this action."
  }
}
```
"""

OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "Health",
        "description": "Service liveness and readiness health check endpoints.",
    },
    {
        "name": "Auth",
        "description": (
            "Registration, JWT login, atomic refresh token rotation, and logout."
        ),
    },
    {
        "name": "Users",
        "description": (
            "User profile management, password change, and Admin user CRUD."
        ),
    },
    {
        "name": "Workspaces",
        "description": (
            "Workspace CRUD, member invitations, and workspace-scoped projects."
        ),
    },
    {
        "name": "Projects",
        "description": (
            "Project management, archiving, Redis-cached tasks, and project labels."
        ),
    },
    {
        "name": "Tasks",
        "description": (
            "Task CRUD, assignment with background notifications, label attachment, "
            "and comments."
        ),
    },
    {
        "name": "Labels",
        "description": "Standalone label deletion operations.",
    },
    {
        "name": "Comments",
        "description": (
            "Standalone comment deletion restricted to author or workspace owner."
        ),
    },
]

_ERROR_CATALOG: dict[int, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorResponse,
        "description": "Bad Request — invalid business rule or foreign reference.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": 400,
                        "message": messages.INVALID_REFERENCE,
                    }
                }
            }
        },
    },
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": (
            "Unauthorized — missing, invalid, expired, or wrong-type Bearer token."
        ),
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": 401,
                        "message": messages.TOKEN_INVALID,
                    }
                }
            }
        },
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": (
            "Forbidden — authenticated user lacks required role or resource ownership."
        ),
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": 403,
                        "message": messages.PERMISSION_DENIED,
                    }
                }
            }
        },
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Not Found — target resource does not exist.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": 404,
                        "message": messages.RESOURCE_NOT_FOUND,
                    }
                }
            }
        },
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Conflict — resource already exists or violates uniqueness.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": 409,
                        "message": messages.DATABASE_CONFLICT,
                    }
                }
            }
        },
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Unprocessable Content — payload or query validation error.",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": 422,
                        "message": messages.VALIDATION_FAILED,
                        "details": [
                            {
                                "field": "body.title",
                                "message": "String should have at least 1 character",
                            }
                        ],
                    }
                }
            }
        },
    },
}


def build_error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Build an OpenAPI responses mapping for the specified HTTP error codes."""
    return {
        code: _ERROR_CATALOG[code] for code in status_codes if code in _ERROR_CATALOG
    }
