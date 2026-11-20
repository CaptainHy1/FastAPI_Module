"""Background task notification utilities for TaskHub events."""

import logging

logger = logging.getLogger("taskhub.notifications")


def send_task_assigned_notification(
    *,
    recipient_id: int,
    task_id: int,
    project_id: int,
    assigned_by_id: int,
) -> None:
    """Simulate dispatching a notification when a task is assigned.

    Executed asynchronously outside the HTTP request/response cycle via
    FastAPI's BackgroundTasks. Logs strictly non-PII identifiers to prevent
    sensitive information leakage in log streams.
    """
    logger.info(
        "Task assignment notification dispatched | recipient_id=%d | task_id=%d | "
        "project_id=%d | assigned_by_id=%d",
        recipient_id,
        task_id,
        project_id,
        assigned_by_id,
    )
