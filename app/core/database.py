"""Database engine and async session configuration using SQLAlchemy 2.0."""

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# Engine creation with fail-safe settings (echo is loaded from Settings, not hardcoded)
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    future=True,
)

if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Annotated dependency alias per trainer guidelines
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def seed_dev_data() -> None:
    """Idempotently seed a default User, Workspace, and Project for Swagger tests."""
    from sqlalchemy import select

    from app.core.constants import ProjectStatus, UserRole, WorkspaceRole
    from app.models import Project, User, Workspace, WorkspaceMember

    async with AsyncSessionLocal() as session:
        existing_user = (
            await session.execute(select(User).limit(1))
        ).scalar_one_or_none()
        if existing_user is not None:
            return

        user = User(
            email="demo@taskhub.dev",
            full_name="Demo User",
            hashed_password="hashed_placeholder_password",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(name="Default Workspace", owner_id=user.id)
        session.add(workspace)
        await session.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        project = Project(
            workspace_id=workspace.id,
            name="TaskHub Core",
            description="Default project for Session 2 task CRUD testing",
            status=ProjectStatus.ACTIVE,
        )
        session.add_all([member, project])
        await session.commit()


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed_dev_data())
