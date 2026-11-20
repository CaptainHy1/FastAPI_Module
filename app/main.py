"""FastAPI Application entrypoint.

Initializes app instance, lifespan context, middleware, exception handlers,
and registers API routers.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.cache import cache_manager
from app.core.config import get_settings
from app.core.constants import (
    HEADER_PROCESS_TIME,
    HEADER_REQUEST_ID,
    Environment,
)
from app.core.database import engine
from app.core.exception_handlers import (
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.openapi import OPENAPI_DESCRIPTION, OPENAPI_TAGS

configure_logging(get_settings().LOG_LEVEL)
logger = logging.getLogger("taskhub")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "Starting up %s (version: %s)...", settings.PROJECT_NAME, settings.VERSION
    )
    logger.info("Running in [%s] environment.", settings.ENVIRONMENT)

    if settings.ENVIRONMENT != Environment.TESTING:
        await cache_manager.connect(
            redis_url=settings.REDIS_URL,
            ttl=settings.CACHE_TTL_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
        )

    yield

    # Shutdown tasks: gracefully close Redis and SQLAlchemy connection pools
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await cache_manager.close()
    await engine.dispose()


def create_application() -> FastAPI:
    """Application factory for TaskHub API."""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=OPENAPI_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS added first so outer RequestLoggingMiddleware logs all requests
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[HEADER_REQUEST_ID, HEADER_PROCESS_TIME],
        )

    # Register HTTP Request Logging & Correlation ID Middleware (outermost layer)
    app.add_middleware(RequestLoggingMiddleware)

    # Register Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount API Routers
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
