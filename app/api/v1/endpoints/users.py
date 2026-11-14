"""User profile and administration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.core import messages
from app.core.dependencies import AdminUser, CurrentUser, UserServiceDep
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    AdminUserUpdate,
    ChangePasswordRequest,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user.",
)
async def get_my_profile(
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserResponse:
    """Get authenticated user profile."""
    return await service.get_profile(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description="Updates display name of the currently authenticated user.",
)
async def update_my_profile(
    payload: UserUpdate,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserResponse:
    """Update authenticated user profile."""
    return await service.update_profile(current_user, payload)


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change current user password",
    description=(
        "Verifies current password, updates password hash, and revokes "
        "all active refresh tokens."
    ),
)
async def change_my_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> MessageResponse:
    """Change authenticated user's password."""
    await service.change_password(current_user, payload)
    return MessageResponse(message=messages.PASSWORD_CHANGED_SUCCESS)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin: update a user",
    description=(
        "Admin-only endpoint to update user full_name, role, or active status. "
        "Protects the last remaining active administrator."
    ),
)
async def admin_update_user(
    user_id: Annotated[int, Path(gt=0, description="Target user ID")],
    payload: AdminUserUpdate,
    admin_user: AdminUser,
    service: UserServiceDep,
) -> UserResponse:
    """Admin user update endpoint."""
    return await service.admin_update_user(admin_user, user_id, payload)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin: delete a user",
    description=(
        "Admin-only endpoint to delete a user. Prevents self-deletion and "
        "protects the last remaining active administrator."
    ),
)
async def admin_delete_user(
    user_id: Annotated[int, Path(gt=0, description="Target user ID")],
    admin_user: AdminUser,
    service: UserServiceDep,
) -> None:
    """Admin user deletion endpoint."""
    await service.admin_delete_user(admin_user, user_id)

