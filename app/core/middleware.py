"""HTTP middleware for structured request logging, timing, and correlation IDs."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.constants import HEADER_PROCESS_TIME, HEADER_REQUEST_ID

logger = logging.getLogger("taskhub.http")


def configure_logging(log_level: str = "INFO") -> None:
    """Configure application-wide structured logging format and level."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("taskhub").setLevel(level)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach correlation ID and process timing headers and log every HTTP request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request, measure latency, inject headers, and emit log entry."""
        request_id = request.headers.get(HEADER_REQUEST_ID) or str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers[HEADER_REQUEST_ID] = request_id
        response.headers[HEADER_PROCESS_TIME] = f"{duration_ms:.2f}ms"

        logger.info(
            "request_id=%s method=%s path=%s status=%d duration=%.2fms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
