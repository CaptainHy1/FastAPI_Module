"""User and RefreshToken repositories using SQLAlchemy 2.x async."""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.constants import UserRole
from app.core.exceptions import ConflictException
from app.models.user import RefreshToken, User
from app.repositories.base import BaseRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserUpdate


class UserRepository(BaseRepository[User, RegisterRequest, UserUpdate]):
    """Async repository for User CRUD and role/admin queries."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=User, db=db)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by normalized lowercase email."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        full_name: str,
        hashed_password: str,
    ) -> User:
        """Insert a new MEMBER user directly and translate duplicate email to 409.

        Relies on DB unique constraint rather than check-before-insert to avoid
        race conditions under concurrent registrations.
        """
        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hashed_password,
            role=UserRole.MEMBER,
            is_active=True,
        )
        self.db.add(user)
        try:
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException(message=messages.EMAIL_ALREADY_EXISTS) from exc
        return user

    async def count_active_admins(self) -> int:
        """Return the number of currently active ADMIN accounts."""
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one())


class RefreshTokenRepository:
    """Async repository for persisted refresh tokens and atomic rotation."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_token(
        self,
        user_id: int,
        jti: str,
        token_hash: str,
        expires_at: datetime,
        *,
        commit: bool = True,
    ) -> RefreshToken:
        """Persist a hashed refresh token record."""
        token_record = RefreshToken(
            user_id=user_id,
            jti=jti,
            token_hash=token_hash,
            revoked=False,
            expires_at=expires_at,
        )
        self.db.add(token_record)
        if commit:
            await self.db.commit()
            await self.db.refresh(token_record)
        return token_record

    async def atomic_revoke_and_get(
        self, token_hash: str
    ) -> tuple[int, int, datetime] | None:
        """Atomically revoke an active refresh token in SQL and return metadata.

        Executes UPDATE ... WHERE revoked = false RETURNING ... so two concurrent
        requests with the same token cannot both succeed.
        Returns (id, user_id, expires_at) if claimed, or None otherwise.
        """
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
            .returning(
                RefreshToken.id,
                RefreshToken.user_id,
                RefreshToken.expires_at,
            )
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return (int(row[0]), int(row[1]), row[2])

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Look up a refresh token record by its SHA-256 hash."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: int, *, commit: bool = False) -> None:
        """Revoke all active refresh tokens belonging to a user."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.db.execute(stmt)
        if commit:
            await self.db.commit()
