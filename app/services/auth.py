"""Authentication business logic service."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.constants import TokenType
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.repositories.user import RefreshTokenRepository, UserRepository
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse


class AuthService:
    """Service handling registration, login, atomic refresh rotation, and logout."""

    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository,
        refresh_repo: RefreshTokenRepository,
    ) -> None:
        self.db = db
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo

    async def _issue_token_pair(
        self, user_id: int, *, commit: bool = True
    ) -> TokenResponse:
        """Create access + refresh tokens and persist hashed refresh token."""
        access_token = create_access_token(user_id)
        raw_refresh, jti, expires_at = create_refresh_token(user_id)
        await self.refresh_repo.create_token(
            user_id=user_id,
            jti=jti,
            token_hash=hash_token(raw_refresh),
            expires_at=expires_at,
            commit=commit,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
        )

    async def register(self, data: RegisterRequest) -> UserResponse:
        """Register a new standard MEMBER user."""
        hashed_pw = hash_password(data.password)
        user = await self.user_repo.create_user(
            email=str(data.email),
            full_name=data.full_name,
            hashed_password=hashed_pw,
        )
        return UserResponse.model_validate(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue JWT access + refresh tokens."""
        user = await self.user_repo.get_by_email(str(data.email))
        if user is None or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException(message=messages.INVALID_CREDENTIALS)

        if not user.is_active:
            raise ForbiddenException(message=messages.INACTIVE_USER)

        return await self._issue_token_pair(user.id, commit=True)

    async def refresh_tokens(self, data: RefreshRequest) -> TokenResponse:
        """Rotate refresh token atomically inside one database transaction.

        If an already-revoked refresh token is reused, revokes all active
        sessions for that user and rejects with 401.
        """
        user_id, _ = decode_token(data.refresh_token, expected_type=TokenType.REFRESH)
        token_hash = hash_token(data.refresh_token)

        claimed = await self.refresh_repo.atomic_revoke_and_get(token_hash)
        if claimed is None:
            existing = await self.refresh_repo.get_by_token_hash(token_hash)
            if existing is not None and existing.revoked:
                await self.refresh_repo.revoke_all_for_user(
                    existing.user_id, commit=True
                )
                raise UnauthorizedException(message=messages.REFRESH_TOKEN_REVOKED)
            raise UnauthorizedException(message=messages.TOKEN_INVALID)

        _, claimed_user_id, expires_at = claimed
        normalized_exp = (
            expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
        )
        if normalized_exp <= datetime.now(UTC):
            await self.db.commit()
            raise UnauthorizedException(message=messages.TOKEN_EXPIRED)

        user = await self.user_repo.get_by_id(claimed_user_id)
        if user is None or user.id != user_id:
            await self.db.commit()
            raise UnauthorizedException(message=messages.TOKEN_INVALID)

        if not user.is_active:
            await self.db.commit()
            raise ForbiddenException(message=messages.INACTIVE_USER)

        # Single transaction: old token revocation + new token insertion commit together
        return await self._issue_token_pair(user.id, commit=True)

    async def logout(self, data: LogoutRequest) -> None:
        """Revoke the provided refresh token to end the session."""
        decode_token(data.refresh_token, expected_type=TokenType.REFRESH)
        token_hash = hash_token(data.refresh_token)
        claimed = await self.refresh_repo.atomic_revoke_and_get(token_hash)
        if claimed is None:
            raise UnauthorizedException(message=messages.REFRESH_TOKEN_REVOKED)
        await self.db.commit()
