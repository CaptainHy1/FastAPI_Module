"""User profile and administrator user management service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.constants import UserRole
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import RefreshTokenRepository, UserRepository
from app.schemas.user import (
    AdminUserUpdate,
    ChangePasswordRequest,
    UserResponse,
    UserUpdate,
)


class UserService:
    """Service for user self-service operations and admin user management."""

    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository,
        refresh_repo: RefreshTokenRepository,
    ) -> None:
        self.db = db
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo

    async def get_profile(self, current_user: User) -> UserResponse:
        """Return authenticated user profile."""
        return UserResponse.model_validate(current_user)

    async def update_profile(
        self, current_user: User, data: UserUpdate
    ) -> UserResponse:
        """Update authenticated user's own profile fields."""
        updated = await self.user_repo.update(current_user.id, obj_in=data)
        if not updated:
            raise NotFoundException(message=messages.USER_NOT_FOUND)
        return UserResponse.model_validate(updated)

    async def change_password(
        self, current_user: User, data: ChangePasswordRequest
    ) -> None:
        """Verify current password, update hash, and revoke all refresh tokens."""
        if not verify_password(data.current_password, current_user.hashed_password):
            raise BadRequestException(message=messages.INVALID_CURRENT_PASSWORD)

        current_user.hashed_password = hash_password(data.new_password)
        await self.refresh_repo.revoke_all_for_user(current_user.id, commit=False)
        await self.db.commit()

    async def admin_update_user(
        self,
        admin_user: User,
        target_user_id: int,
        data: AdminUserUpdate,
    ) -> UserResponse:
        """Admin-only update protecting self-demotion/deactivation and last admin."""
        target_user = await self.user_repo.get_by_id(target_user_id)
        if not target_user:
            raise NotFoundException(message=messages.USER_NOT_FOUND)

        if target_user.id == admin_user.id:
            if data.is_active is False:
                raise BadRequestException(message=messages.CANNOT_DEACTIVATE_SELF)
            if data.role is not None and data.role != UserRole.ADMIN:
                raise BadRequestException(message=messages.CANNOT_DEMOTE_SELF)

        is_demoting = data.role is not None and data.role != UserRole.ADMIN
        is_deactivating = data.is_active is False
        if (
            target_user.role == UserRole.ADMIN
            and target_user.is_active
            and (is_demoting or is_deactivating)
            and await self.user_repo.count_active_admins() <= 1
        ):
            raise BadRequestException(message=messages.LAST_ADMIN_PROTECTED)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(target_user, field, value)

        if is_deactivating:
            await self.refresh_repo.revoke_all_for_user(target_user.id, commit=False)

        await self.db.commit()
        await self.db.refresh(target_user)
        return UserResponse.model_validate(target_user)

    async def admin_delete_user(self, admin_user: User, target_user_id: int) -> None:
        """Admin-only delete protecting self-deletion and last active admin."""
        if target_user_id == admin_user.id:
            raise BadRequestException(message=messages.CANNOT_DELETE_SELF)

        target_user = await self.user_repo.get_by_id(target_user_id)
        if not target_user:
            raise NotFoundException(message=messages.USER_NOT_FOUND)

        if (
            target_user.role == UserRole.ADMIN
            and target_user.is_active
            and await self.user_repo.count_active_admins() <= 1
        ):
            raise BadRequestException(message=messages.LAST_ADMIN_PROTECTED)

        await self.user_repo.delete(target_user_id)
