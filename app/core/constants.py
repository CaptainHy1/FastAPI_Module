"""Application constants and enumerations.

Eliminates magic strings across the codebase as required by coding standards.
"""

from enum import StrEnum

# ==============================================================================
# Security & Password Constants
# ==============================================================================
MIN_PASSWORD_LENGTH: int = 8
MAX_PASSWORD_BYTES: int = 72  # Strict bcrypt limit (bytes, not characters)
DEFAULT_JWT_ALGORITHM: str = "HS256"


# ==============================================================================
# Token Types
# ==============================================================================
class TokenType(StrEnum):
    """JWT token types for claim validation."""

    ACCESS = "access"
    REFRESH = "refresh"


# ==============================================================================
# Domain Enumerations (TaskHub Schema)
# ==============================================================================
class UserRole(StrEnum):
    """User system role."""

    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class WorkspaceRole(StrEnum):
    """Workspace membership role."""

    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class ProjectStatus(StrEnum):
    """Project lifecycle status."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class TaskStatus(StrEnum):
    """Task workflow status."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"


class TaskPriority(StrEnum):
    """Task priority levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


# ==============================================================================
# Pagination Defaults
# ==============================================================================
DEFAULT_PAGE: int = 1
DEFAULT_PAGE_SIZE: int = 10
MAX_PAGE_SIZE: int = 100
