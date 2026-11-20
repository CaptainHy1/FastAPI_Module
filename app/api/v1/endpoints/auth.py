"""Authentication endpoints: register, login, refresh rotation, and logout."""

from fastapi import APIRouter, status

from app.core import messages
from app.core.dependencies import AuthServiceDep
from app.core.openapi import build_error_responses
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses=build_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Register a new user",
    description=(
        "Creates a new MEMBER account. Role cannot be chosen by the client. "
        "Duplicate emails return 409 Conflict."
    ),
)
async def register(
    payload: RegisterRequest,
    service: AuthServiceDep,
) -> UserResponse:
    """Register user endpoint."""
    return await service.register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="User login",
    description="Authenticates credentials and issues JWT access and refresh tokens.",
)
async def login(
    payload: LoginRequest,
    service: AuthServiceDep,
) -> TokenResponse:
    """Login user endpoint."""
    return await service.login(payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Rotate refresh token",
    description=(
        "Atomically revokes the current refresh token and issues a new token pair. "
        "Reusing a revoked token revokes all active user sessions."
    ),
)
async def refresh_token(
    payload: RefreshRequest,
    service: AuthServiceDep,
) -> TokenResponse:
    """Refresh token rotation endpoint."""
    return await service.refresh_tokens(payload)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    responses=build_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary="Logout user",
    description="Revokes the provided refresh token.",
)
async def logout(
    payload: LogoutRequest,
    service: AuthServiceDep,
) -> MessageResponse:
    """Logout user endpoint."""
    await service.logout(payload)
    return MessageResponse(message=messages.LOGOUT_SUCCESS)
