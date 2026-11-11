"""Authentication Pydantic v2 schemas and shared password validators."""

from pydantic import EmailStr, Field, field_validator

from app.core import messages
from app.core.constants import (
    BEARER_TOKEN_TYPE,
    MAX_EMAIL_LENGTH,
    MAX_FULL_NAME_LENGTH,
    MAX_PASSWORD_BYTES,
    MIN_FULL_NAME_LENGTH,
    MIN_PASSWORD_LENGTH,
)
from app.schemas.base import AppBaseModel


def validate_password_max_bytes(value: str) -> str:
    """Enforce bcrypt's strict 72-byte UTF-8 input limit."""
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(messages.PASSWORD_TOO_LONG_BYTES)
    return value


def validate_new_password(value: str) -> str:
    """Validate minimum length and bcrypt 72-byte UTF-8 ceiling for new passwords."""
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(messages.PASSWORD_TOO_SHORT)
    return validate_password_max_bytes(value)


class RegisterRequest(AppBaseModel):
    """Schema for registering a new user account.

    Role is intentionally excluded so clients cannot self-assign privileged roles.
    """

    email: EmailStr = Field(
        ...,
        max_length=MAX_EMAIL_LENGTH,
        description="Unique user email address",
        examples=["user@taskhub.dev"],
    )
    full_name: str = Field(
        ...,
        min_length=MIN_FULL_NAME_LENGTH,
        max_length=MAX_FULL_NAME_LENGTH,
        description="User display name",
        examples=["Nguyen Van A"],
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        description="Plain-text password (min 8 chars, max 72 UTF-8 bytes)",
        examples=["StrongPass123!"],
    )

    @field_validator("password", mode="after")
    @classmethod
    def check_password_policy(cls, v: str) -> str:
        return validate_new_password(v)


class LoginRequest(AppBaseModel):
    """Schema for user login credentials."""

    email: EmailStr = Field(
        ...,
        max_length=MAX_EMAIL_LENGTH,
        description="Registered user email",
        examples=["user@taskhub.dev"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password (max 72 UTF-8 bytes)",
        examples=["StrongPass123!"],
    )

    @field_validator("password", mode="after")
    @classmethod
    def check_password_bytes(cls, v: str) -> str:
        return validate_password_max_bytes(v)


class RefreshRequest(AppBaseModel):
    """Schema for rotating refresh token."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Valid JWT refresh token",
    )


class LogoutRequest(AppBaseModel):
    """Schema for logging out by revoking refresh token."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Refresh token to revoke",
    )


class TokenResponse(AppBaseModel):
    """JWT access and refresh token pair returned on login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = BEARER_TOKEN_TYPE


class MessageResponse(AppBaseModel):
    """Generic status message response."""

    message: str

