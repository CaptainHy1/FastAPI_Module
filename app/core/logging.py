"""Application-wide structured logging configuration with ContextVar correlation ID."""

import logging
from contextvars import ContextVar

# Context variable carrying the active request correlation ID across async tasks
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Logging filter injecting active request correlation ID into LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject %(request_id)s attribute into the log record."""
        record.request_id = request_id_ctx.get()
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """Configure application-wide logging format with correlation ID support."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    log_format = (
        "%(asctime)s [%(levelname)s] [req_id=%(request_id)s] %(name)s: %(message)s"
    )

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter(log_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Clear existing handlers to prevent duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("taskhub").setLevel(level)
