"""Centralized user-facing messages.

Prevents hardcoded strings in routers, services, and dependencies.
"""

# Health & System
HEALTH_CHECK_OK: str = "TaskHub API is up and running."

# Tasks
TASK_NOT_FOUND: str = "Task not found."
TASK_TITLE_REQUIRED: str = "Task title cannot be empty."
TASK_DELETED_SUCCESS: str = "Task deleted successfully."

# Authentication & Authorization (Prepared for Auth Session)
INACTIVE_USER: str = "User account is inactive."
INVALID_CREDENTIALS: str = "Incorrect email or password."
EMAIL_ALREADY_EXISTS: str = "Email is already registered."
TOKEN_EXPIRED: str = "Authentication token has expired."
TOKEN_INVALID: str = "Could not validate credentials."
INVALID_TOKEN_TYPE: str = "Invalid token type provided."
REFRESH_TOKEN_REVOKED: str = "Refresh token has been revoked."

# Permissions & RBAC
PERMISSION_DENIED: str = "You do not have permission to perform this action."
CANNOT_DELETE_SELF: str = "Administrators cannot delete their own account."
LAST_ADMIN_PROTECTED: str = (
    "Cannot remove or deactivate the last remaining active administrator."
)

# Common / Generic
INTERNAL_SERVER_ERROR: str = "An unexpected error occurred. Please try again later."
RESOURCE_NOT_FOUND: str = "The requested resource was not found."
VALIDATION_FAILED: str = "Request validation failed."
DATABASE_CONFLICT: str = "Resource conflict occurred."
INVALID_REFERENCE: str = "Referenced project or user does not exist."
