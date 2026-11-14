"""Centralized user-facing messages.

Prevents hardcoded strings in routers, services, and dependencies.
"""

from app.core.constants import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH

# Health & System
HEALTH_CHECK_OK: str = "TaskHub API is up and running."

# Tasks
TASK_NOT_FOUND: str = "Task not found."
TASK_TITLE_REQUIRED: str = "Task title cannot be empty."
TASK_DELETED_SUCCESS: str = "Task deleted successfully."

# Authentication & Authorization
INACTIVE_USER: str = "User account is inactive."
INVALID_CREDENTIALS: str = "Incorrect email or password."
EMAIL_ALREADY_EXISTS: str = "Email is already registered."
TOKEN_EXPIRED: str = "Authentication token has expired."
TOKEN_INVALID: str = "Could not validate credentials."
INVALID_TOKEN_TYPE: str = "Invalid token type provided."
REFRESH_TOKEN_REVOKED: str = "Refresh token has been revoked."
INVALID_CURRENT_PASSWORD: str = "Current password is incorrect."
PASSWORD_TOO_SHORT: str = (
    f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
)
PASSWORD_TOO_LONG_BYTES: str = f"Password must not exceed {MAX_PASSWORD_BYTES} bytes."
PASSWORD_CHANGED_SUCCESS: str = "Password changed successfully."
LOGOUT_SUCCESS: str = "Logged out successfully."

# Permissions & RBAC
USER_NOT_FOUND: str = "User not found."
PERMISSION_DENIED: str = "You do not have permission to perform this action."
CANNOT_DELETE_SELF: str = "Administrators cannot delete their own account."
CANNOT_DEACTIVATE_SELF: str = "Administrators cannot deactivate their own account."
CANNOT_DEMOTE_SELF: str = "Administrators cannot remove their own admin role."
LAST_ADMIN_PROTECTED: str = (
    "Cannot remove or deactivate the last remaining active administrator."
)

# Workspace & Project RBAC Messages
WORKSPACE_NOT_FOUND: str = "Workspace not found."
WORKSPACE_OWNER_REQUIRED: str = "Only workspace owner can perform this operation."
NOT_WORKSPACE_MEMBER: str = "You are not a member of this workspace."
PROJECT_NOT_FOUND: str = "Project not found."
PROJECT_EDITOR_REQUIRED: str = (
    "Only workspace owner or editor can perform this operation on projects."
)
TASK_EDITOR_REQUIRED: str = (
    "Only workspace owner or editor can perform this operation on tasks."
)
MEMBER_ALREADY_EXISTS: str = "User is already a member of this workspace."
MEMBER_NOT_FOUND: str = "Workspace member not found."
CANNOT_REMOVE_WORKSPACE_OWNER: str = (
    "Cannot remove or transfer out the primary workspace owner."
)

# Common / Generic
INTERNAL_SERVER_ERROR: str = "An unexpected error occurred. Please try again later."
RESOURCE_NOT_FOUND: str = "The requested resource was not found."
VALIDATION_FAILED: str = "Request validation failed."
DATABASE_CONFLICT: str = "Resource conflict occurred."
INVALID_REFERENCE: str = "Referenced project or user does not exist."
