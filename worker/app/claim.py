"""Take one queued ticket so this worker is the only one processing it.

The claim is one statement: SELECT ... FOR UPDATE SKIP LOCKED, then an update
that moves the row to processing. Another worker skips a ticket that is already
locked. The attempt count stored on the row is the attempt now in progress.
A ticket whose next_attempt_at is still in the future stays queued.
"""

from dataclasses import dataclass

from sqlalchemy import text

from desktriage_common.db import get_session
from desktriage_common.logging import get_logger
from desktriage_common.statuses import Status

logger = get_logger("worker.claim")

_CLAIM_TICKET = text(
    """
    WITH next_ticket AS (
        SELECT ticket_id
        FROM tickets
        WHERE status = :queued
          AND (next_attempt_at IS NULL OR next_attempt_at <= now())
        ORDER BY next_attempt_at, created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    UPDATE tickets
    SET status = :processing,
        attempt_count = attempt_count + 1,
        claimed_at = now(),
        updated_at = now(),
        next_attempt_at = NULL
    FROM next_ticket
    WHERE tickets.ticket_id = next_ticket.ticket_id
    RETURNING
        tickets.ticket_id,
        tickets.user_id,
        tickets.query_text,
        tickets.escalation_reason,
        tickets.attempt_count
    """
)


@dataclass(frozen=True)
class ClaimedTicket:
    """A ticket reserved for this worker, with the attempt now in progress."""

    ticket_id: str
    user_id: str
    query_text: str
    escalation_reason: str
    attempt: int


def claim_ticket() -> ClaimedTicket | None:
    """Claim the next eligible queued ticket, or return None when none is waiting.

    Due retries come before tickets that have never been scheduled. Within
    each of those groups, the earlier created_at wins. That is the order of
    the queued-ticket index.

    The session commits before this returns, so the row is processing and the
    lock is released before the pipeline runs. The attempt on the result is the
    incremented attempt_count.
    """
    with get_session() as session:
        row = session.execute(
            _CLAIM_TICKET,
            {
                "queued": Status.QUEUED.value,
                "processing": Status.PROCESSING.value,
            },
        ).mappings().one_or_none()
    if row is None:
        return None

    claimed = ClaimedTicket(
        ticket_id=row["ticket_id"],
        user_id=row["user_id"],
        query_text=row["query_text"],
        escalation_reason=row["escalation_reason"],
        attempt=row["attempt_count"],
    )
    logger.info(
        "event=ticket_claimed ticket_id=%s attempt=%s",
        claimed.ticket_id,
        claimed.attempt,
    )
    return claimed
