"""Application configuration and settings using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import DEFAULT_JWT_ALGORITHM


class Settings(BaseSettings):
    """Application settings with fail-fast validation.

    Loads values from environment variables or .env file.
    """

    # General App Info
    PROJECT_NAME: str = "TaskHub API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = (
        "development"
    )
    DEBUG: bool = True

    # Security & JWT
    # Enforces minimum 32 chars to fail fast if key is insecure or empty
    SECRET_KEY: str = Field(
        default="",
        min_length=32,
        description="Cryptographic secret key for signing JWT tokens",
    )
    ALGORITHM: str = DEFAULT_JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Configuration (echo from settings, not hardcoded)
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5433/taskhub_dev"
    )
    DB_ECHO: bool = False

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated or JSON string of allowed CORS origins."""
        val = self.ALLOWED_ORIGINS.strip()
        if val.startswith("[") and val.endswith("]"):
            import json

            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                pass
        return [origin.strip() for origin in val.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        str_strip_whitespace=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
