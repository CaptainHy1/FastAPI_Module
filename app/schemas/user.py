"""User profile and administration Pydantic v2 schemas."""

from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field, ValidationInfo, field_validator

from app.core.constants import (
    MAX_FULL_NAME_LENGTH,
    MIN_FULL_NAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    UserRole,
)
from app.schemas.auth import validate_new_password, validate_password_max_bytes
from app.schemas.base import AppBaseModel


class UserResponse(AppBaseModel):
    """Public user representation returned by API endpoints."""

    id: int = Field(..., gt=0)
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserUpdate(AppBaseModel):
    """Schema for self-service profile update (PATCH /users/me)."""

    full_name: str | None = Field(
        default=None,
        min_length=MIN_FULL_NAME_LENGTH,
        max_length=MAX_FULL_NAME_LENGTH,
        description="Updated full name",
    )

    @field_validator("full_name", mode="after")
    @classmethod
    def reject_null_full_name(cls, v: Any, info: ValidationInfo) -> Any:
        """Reject explicit null for NOT NULL column full_name."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class AdminUserUpdate(AppBaseModel):
    """Schema for administrator user updates (PATCH /users/{user_id})."""

    full_name: str | None = Field(
        default=None,
        min_length=MIN_FULL_NAME_LENGTH,
        max_length=MAX_FULL_NAME_LENGTH,
    )
    role: UserRole | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    @field_validator("full_name", "role", "is_active", mode="after")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, v: Any, info: ValidationInfo) -> Any:
        """Reject explicit null for NOT NULL user columns."""
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class ChangePasswordRequest(AppBaseModel):
    """Schema for changing authenticated user's password."""

    current_password: str = Field(
        ...,
        min_length=1,
        description="Existing password (max 72 UTF-8 bytes)",
    )
    new_password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        description="New password (min 8 chars, max 72 UTF-8 bytes)",
    )

    @field_validator("current_password", mode="after")
    @classmethod
    def check_current_password_bytes(cls, v: str) -> str:
        return validate_password_max_bytes(v)

    @field_validator("new_password", mode="after")
    @classmethod
    def check_new_password_policy(cls, v: str) -> str:
        return validate_new_password(v)
