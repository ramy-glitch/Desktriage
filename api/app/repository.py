"""Persist a new ticket and read it back by its public id.

Insert the ticket with status queued and return the id the assistant will poll.
The intake response reports the accepted status. A later read returns the
lifecycle value stored on the row and, once the worker has finished, the stored
decision. This module does not classify or route.
"""

import uuid
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.orm import Session

from common.desktriage_common.db import get_session
from common.desktriage_common.schemas import (
    TicketAccepted,
    TicketIngest,
    TicketStatus,
    TriageDecision,
)
from common.desktriage_common.statuses import Status

from .errors import TicketStoreError

_FINISHED = {Status.ROUTED, Status.NEEDS_HUMAN_REVIEW}

_INSERT_TICKET = text(
    """
    INSERT INTO tickets (
        ticket_id,
        user_id,
        query_text,
        escalation_reason,
        status
    )
    VALUES (
        :ticket_id,
        :user_id,
        :query_text,
        :escalation_reason,
        :status
    )
    """
)

_SELECT_TICKET = text(
    """
    SELECT
        tickets.ticket_id,
        tickets.status,
        decisions.category,
        decisions.priority,
        decisions.confidence,
        decisions.requires_human_review,
        decisions.destination,
        decisions.model_version
    FROM tickets
    LEFT JOIN LATERAL (
        SELECT
            category,
            priority,
            confidence,
            requires_human_review,
            destination,
            model_version
        FROM triage_decisions
        WHERE triage_decisions.ticket_id = tickets.ticket_id
        ORDER BY decided_at DESC, id DESC
        LIMIT 1
    ) AS decisions ON true
    WHERE tickets.ticket_id = :ticket_id
    """
)


def insert_ticket(ticket: TicketIngest) -> TicketAccepted:
    """Store the escalated query as queued and return the id to poll.

    The returned status is accepted. The row is queued so the worker can
    claim it. Category, priority, and assigned team are not written here.
    A failed insert is rolled back and raised as TicketStoreError, so no
    ticket id is returned for a row the worker could claim.
    """
    accepted = TicketAccepted(ticket_id=str(uuid.uuid4()))
    try:
        with get_session() as session:
            session.execute(
                _INSERT_TICKET,
                {
                    "ticket_id": accepted.ticket_id,
                    "user_id": ticket.user_id,
                    "query_text": ticket.query_text,
                    "escalation_reason": ticket.escalation_reason,
                    "status": Status.QUEUED.value,
                },
            )
    except Exception as exc:
        raise TicketStoreError("the ticket was not stored") from exc
    return accepted


def get_ticket(ticket_id: str) -> TicketStatus | None:
    """Return the stored ticket, or None when the id is unknown.

    Queued, processing, and failed tickets have no decision. A routed or
    human-review ticket includes the latest decision the worker stored.
    """
    with get_session() as session:
        return _read_ticket(session, ticket_id)


def _read_ticket(session: Session, ticket_id: str) -> TicketStatus | None:
    row = session.execute(_SELECT_TICKET, {"ticket_id": ticket_id}).mappings().one_or_none()
    if row is None:
        return None
    status = Status(row["status"])
    decision = _decision(row) if status in _FINISHED else None
    return TicketStatus(ticket_id=row["ticket_id"], status=status, decision=decision)


def _decision(row: Mapping[str, object]) -> TriageDecision:
    return TriageDecision(
        category=row["category"],
        priority=row["priority"],
        confidence=row["confidence"],
        requires_human_review=row["requires_human_review"],
        destination=row["destination"],
        model_version=row["model_version"],
    )
