"""Pytest fixtures and async SQLite database configuration."""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set testing environment variables before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.core.constants import ProjectStatus, UserRole, WorkspaceRole
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base, Project, User, Workspace, WorkspaceMember

_DEMO_ADMIN_PASSWORD_HASH = hash_password("Admin1234!")

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield isolated test database session."""
    async with TestingSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_test_database() -> AsyncGenerator[None, None]:
    """Create tables and seed base User/Workspace/Project before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        user = User(
            id=1,
            email="demo@taskhub.dev",
            full_name="Demo User",
            hashed_password=_DEMO_ADMIN_PASSWORD_HASH,
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(id=1, name="Default Workspace", owner_id=user.id)
        session.add(workspace)
        await session.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        project = Project(
            id=1,
            workspace_id=workspace.id,
            name="TaskHub Core",
            status=ProjectStatus.ACTIVE,
        )
        session.add_all([member, project])
        await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide direct AsyncSession fixture for repository/ORM relationship tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client configured with test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
