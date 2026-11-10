"""Pytest fixtures and configuration."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# Set testing environment variables before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"

from app.core.dependencies import get_task_repository
from app.main import app


@pytest.fixture(autouse=True)
def reset_repository() -> None:
    """Clear repository before each test to ensure test isolation."""
    repo = get_task_repository()
    repo._storage.clear()
    repo._current_id = 0


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client configured with test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
