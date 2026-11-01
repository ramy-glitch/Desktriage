"""Poll for queued work until the process is asked to stop.

Claim one ticket, pass it to pipeline.py, then wait before polling again.
An empty queue waits too, so the process does not spin. When a ticket fails,
the row stays in the database and retry.py decides when it is eligible again.
"""

from collections.abc import Callable
from time import sleep

from desktriage_common.logging import get_logger

from worker.app.claim import ClaimedTicket, claim_ticket

logger = get_logger("worker.loop")

POLL_INTERVAL_SECONDS = 1.0


def run(
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stop: Callable[[], bool] | None = None,
) -> None:
    """Claim and hand off one ticket at a time until stop returns true."""
    if isinstance(poll_interval, bool) or not isinstance(poll_interval, (int, float)):
        raise ValueError("poll_interval must be a positive number of seconds")
    if poll_interval <= 0:
        raise ValueError("poll_interval must be a positive number of seconds")

    while not _should_stop(stop):
        try:
            claimed = claim_ticket()
        except Exception as exc:
            logger.error("event=claim_failed error_type=%s", type(exc).__name__)
            if _should_stop(stop):
                return
            sleep(poll_interval)
            continue
        if claimed is not None:
            _handoff(claimed)
        if _should_stop(stop):
            return
        sleep(poll_interval)


def _handoff(claimed: ClaimedTicket) -> None:
    try:
        _process_ticket(claimed)
    except Exception as exc:
        logger.error(
            "event=ticket_failed ticket_id=%s attempt=%s error_type=%s",
            claimed.ticket_id,
            claimed.attempt,
            type(exc).__name__,
        )
        _ask_retry(claimed, exc)


def _ask_retry(claimed: ClaimedTicket, exc: Exception) -> None:
    try:
        _schedule_retry(claimed, exc)
    except Exception as retry_exc:
        logger.error(
            "event=retry_failed ticket_id=%s attempt=%s error_type=%s",
            claimed.ticket_id,
            claimed.attempt,
            type(retry_exc).__name__,
        )


def _process_ticket(claimed: ClaimedTicket) -> None:
    from worker.app.pipeline import process_ticket

    process_ticket(claimed)


def _schedule_retry(claimed: ClaimedTicket, exc: Exception) -> None:
    from worker.app.retry import schedule_retry

    schedule_retry(claimed, exc)


def _should_stop(stop: Callable[[], bool] | None) -> bool:
    return stop is not None and stop()
