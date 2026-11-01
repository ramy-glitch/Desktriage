"""Decide what happens when classification, storage, or notification fails.

Claim has already counted the attempt now in progress, so this module keeps
that count and keeps the ticket row. Below the attempt limit, the row returns
to queued with a next_attempt_at the loop will not claim before. At the limit,
the status becomes failed. A failed ticket stays in the database, so the status
route can still read it.
"""

from dataclasses import dataclass

from sqlalchemy import text

from desktriage_common.db import get_session
from desktriage_common.logging import get_logger, log_retry
from desktriage_common.statuses import Status

from worker.app.claim import ClaimedTicket

logger = get_logger("worker.retry")

# Three claims of the same ticket, then the row is failed and left readable.
ATTEMPT_LIMIT = 3
# Attempt 1 waits 5 seconds. Attempt 2 waits 10. The third claim does not wait.
RETRY_BACKOFF_SECONDS = 5

_RETRYABLE = (
    Status.PROCESSING.value,
    Status.ROUTED.value,
    Status.NEEDS_HUMAN_REVIEW.value,
)

_REQUEUE_TICKET = text(
    """
    UPDATE tickets
    SET status = :status,
        next_attempt_at = now() + make_interval(secs => :delay_seconds),
        updated_at = now()
    WHERE ticket_id = :ticket_id
      AND status IN (:processing, :routed, :needs_human_review)
    RETURNING ticket_id
    """
)

_FAIL_TICKET = text(
    """
    UPDATE tickets
    SET status = :status,
        next_attempt_at = NULL,
        updated_at = now()
    WHERE ticket_id = :ticket_id
      AND status IN (:processing, :routed, :needs_human_review)
    RETURNING ticket_id
    """
)


class RetryError(ValueError):
    """The failed attempt cannot be rescheduled."""


@dataclass(frozen=True)
class RetryPlan:
    """What was written for one failed attempt."""

    ticket_id: str
    attempt: int
    status: Status
    delay_seconds: int | None


def schedule_retry(claimed: ClaimedTicket, exc: Exception) -> RetryPlan:
    """Requeue the ticket, or mark it failed when the attempt limit is reached.

    The attempt count is left as claim stored it. A routed or human-review row
    can still be rescheduled, because notification runs after the decision write
    and a delivery failure has to be claimed again.
    """
    ticket_id = _ticket_id(claimed.ticket_id)
    attempt = _attempt(claimed.attempt)
    if not isinstance(exc, Exception):
        raise RetryError("retry needs the failure that stopped the attempt")

    if attempt >= ATTEMPT_LIMIT:
        _update(
            _FAIL_TICKET,
            ticket_id=ticket_id,
            status=Status.FAILED.value,
            delay_seconds=None,
        )
        logger.error(
            "event=ticket_exhausted ticket_id=%s attempt=%s error_type=%s",
            ticket_id,
            attempt,
            type(exc).__name__,
        )
        return RetryPlan(
            ticket_id=ticket_id,
            attempt=attempt,
            status=Status.FAILED,
            delay_seconds=None,
        )

    delay_seconds = RETRY_BACKOFF_SECONDS * attempt
    _update(
        _REQUEUE_TICKET,
        ticket_id=ticket_id,
        status=Status.QUEUED.value,
        delay_seconds=delay_seconds,
    )
    log_retry(
        logger,
        ticket_id=ticket_id,
        attempt=attempt,
        error_type=type(exc).__name__,
    )
    return RetryPlan(
        ticket_id=ticket_id,
        attempt=attempt,
        status=Status.QUEUED,
        delay_seconds=delay_seconds,
    )


def _update(statement: object, *, ticket_id: str, status: str, delay_seconds: int | None) -> None:
    params = {
        "ticket_id": ticket_id,
        "status": status,
        "processing": _RETRYABLE[0],
        "routed": _RETRYABLE[1],
        "needs_human_review": _RETRYABLE[2],
    }
    if delay_seconds is not None:
        params["delay_seconds"] = delay_seconds
    with get_session() as session:
        updated = session.execute(statement, params).mappings().one_or_none()
    if updated is None:
        raise RetryError("the ticket is not waiting on a retry")


def _ticket_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetryError("ticket_id must not be empty")
    return value.strip()


def _attempt(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RetryError("attempt must be a positive integer")
    return value
