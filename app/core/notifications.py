"""Background task notification utilities for TaskHub events."""

import logging

logger = logging.getLogger("taskhub.notifications")


def send_task_assigned_notification(
    *,
    recipient_email: str,
    recipient_name: str,
    task_id: int,
    task_title: str,
    project_id: int,
    assigned_by_email: str,
) -> None:
    """Simulate dispatching an email notification when a task is assigned.

    Executed asynchronously outside the HTTP request/response cycle via
    FastAPI's BackgroundTasks so API latency is unaffected.
    """
    logger.info(
        "Email notification sent | to=%s (%s) | task_id=%d | title='%s' | "
        "project_id=%d | assigned_by=%s",
        recipient_email,
        recipient_name,
        task_id,
        task_title,
        project_id,
        assigned_by_email,
    )
