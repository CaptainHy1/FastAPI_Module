"""Pure ASGI HTTP middleware for request logging, timing, and correlation IDs."""

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.constants import (
    HEADER_PROCESS_TIME,
    HEADER_REQUEST_ID,
    REQUEST_ID_MAX_LENGTH,
    REQUEST_ID_PATTERN,
)
from app.core.logging import request_id_ctx

logger = logging.getLogger("taskhub.http")
_REQUEST_ID_REGEX = re.compile(REQUEST_ID_PATTERN)


class RequestLoggingMiddleware:
    """Pure ASGI middleware attaching correlation IDs and measuring latency."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI scope, validate correlation ID, and record execution metrics."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract and validate incoming X-Request-ID (prevent CRLF injection)
        raw_id: str | None = None
        for key, value in scope.get("headers", []):
            if key.decode("latin1").lower() == HEADER_REQUEST_ID.lower():
                try:
                    raw_id = value.decode("utf-8")
                except UnicodeDecodeError:
                    raw_id = None
                break

        if (
            raw_id
            and len(raw_id) <= REQUEST_ID_MAX_LENGTH
            and _REQUEST_ID_REGEX.match(raw_id)
        ):
            request_id = raw_id
        else:
            request_id = str(uuid.uuid4())

        # Set ContextVar for application-wide logging correlation
        token = request_id_ctx.set(request_id)
        scope["state"] = scope.get("state", {})
        scope["state"]["request_id"] = request_id

        start_time = time.perf_counter()
        status_code = 500  # Default to 500 in case an unhandled exception escapes

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[HEADER_REQUEST_ID] = request_id
                duration_ms = (time.perf_counter() - start_time) * 1000
                headers[HEADER_PROCESS_TIME] = f"{duration_ms:.2f}ms"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "request_id=%s method=%s path=%s status=500 duration=%.2fms",
                request_id,
                scope.get("method", "UNKNOWN"),
                scope.get("path", ""),
                duration_ms,
            )
            raise
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "request_id=%s method=%s path=%s status=%d duration=%.2fms",
                request_id,
                scope.get("method", "UNKNOWN"),
                scope.get("path", ""),
                status_code,
                duration_ms,
            )
        finally:
            request_id_ctx.reset(token)
