"""Custom application exceptions hierarchy.

All service-level and domain-level exceptions inherit from AppException.
Global exception handlers map these to clean HTTP responses.
"""

from typing import Any

from app.core import messages


class AppException(Exception):
    """Base class for all application-specific exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}
        self.extra = extra or {}


class NotFoundException(AppException):
    """Raised when an entity or resource is not found (404)."""

    def __init__(
        self,
        message: str = messages.RESOURCE_NOT_FOUND,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=404, extra=extra)


class BadRequestException(AppException):
    """Raised when client sends invalid parameters or payload (400)."""

    def __init__(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=400, extra=extra)


class UnauthorizedException(AppException):
    """Raised when authentication fails (401).

    Maintains WWW-Authenticate: Bearer header per RFC 6750 & trainer requirements.
    """

    def __init__(
        self,
        message: str = messages.TOKEN_INVALID,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            extra=extra,
        )


class ForbiddenException(AppException):
    """Raised when user lacks permission to access or modify a resource (403)."""

    def __init__(
        self,
        message: str = messages.PERMISSION_DENIED,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=403, extra=extra)


class ConflictException(AppException):
    """Raised on state conflicts such as duplicate email (409)."""

    def __init__(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=409, extra=extra)


class UnprocessableEntityException(AppException):
    """Raised when semantic validation fails (422)."""

    def __init__(
        self,
        message: str = messages.VALIDATION_FAILED,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=422, extra=extra)
