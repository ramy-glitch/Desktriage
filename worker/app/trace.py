"""Store the triage outcome for one ticket.

Record the predicted category, priority, confidence, human-review flag,
routing destination, and the model version reported by the loader.
The status route reads this record back. One finished attempt produces one
decision, and the ticket leaves processing in the same commit.
"""

from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import text

from desktriage_common.db import get_session
from desktriage_common.enums import Category, Priority
from desktriage_common.logging import get_logger, log_routing_outcome
from desktriage_common.schemas import TriageDecision
from desktriage_common.statuses import Status

from worker.app.classifier.loader import model_version

logger = get_logger("worker.trace")

_FINISH_TICKET = text(
    """
    UPDATE tickets
    SET status = :status,
        updated_at = now()
    WHERE ticket_id = :ticket_id
      AND status = :processing
    RETURNING ticket_id
    """
)

_INSERT_DECISION = text(
    """
    INSERT INTO triage_decisions (
        ticket_id,
        category,
        priority,
        confidence,
        requires_human_review,
        destination,
        routing_outcome,
        model_version
    )
    VALUES (
        :ticket_id,
        :category,
        :priority,
        :confidence,
        :requires_human_review,
        :destination,
        :routing_outcome,
        :model_version
    )
    """
)


class TraceError(ValueError):
    """The decision cannot be stored for this ticket."""


@dataclass(frozen=True)
class StoredDecision:
    """The decision written for one finished attempt, and the status it set."""

    ticket_id: str
    status: Status
    decision: TriageDecision


def record_decision(
    ticket_id: str,
    *,
    category: Category | str,
    priority: Priority | str,
    confidence: float,
    requires_human_review: bool,
    destination: str | None,
) -> StoredDecision:
    """Write one decision and set the ticket to routed or needs_human_review.

    The model version is the loader's hash of classifier.keras. A human-review
    decision stores no destination. A second call does not write another row:
    the ticket is no longer processing, so the update matches nothing.
    """
    if not isinstance(ticket_id, str) or not ticket_id.strip():
        raise TraceError("ticket_id must not be empty")
    if not isinstance(requires_human_review, bool):
        raise TraceError("requires_human_review must be true or false")

    try:
        decision = TriageDecision(
            category=category,
            priority=priority,
            confidence=confidence,
            requires_human_review=requires_human_review,
            destination=destination,
            model_version=model_version(),
        )
    except ValidationError as exc:
        raise TraceError("the decision does not match the stored outcome") from exc

    status = Status.NEEDS_HUMAN_REVIEW if decision.requires_human_review else Status.ROUTED
    ticket_id = ticket_id.strip()
    with get_session() as session:
        updated = session.execute(
            _FINISH_TICKET,
            {
                "ticket_id": ticket_id,
                "status": status.value,
                "processing": Status.PROCESSING.value,
            },
        ).mappings().one_or_none()
        if updated is None:
            raise TraceError("the ticket is not processing")
        session.execute(
            _INSERT_DECISION,
            {
                "ticket_id": ticket_id,
                "category": decision.category.value,
                "priority": decision.priority.value,
                "confidence": decision.confidence,
                "requires_human_review": decision.requires_human_review,
                "destination": decision.destination,
                "routing_outcome": status.value,
                "model_version": decision.model_version,
            },
        )

    log_routing_outcome(
        logger,
        ticket_id=ticket_id,
        status=status,
        category=decision.category,
        priority=decision.priority,
        destination=decision.destination,
        confidence=decision.confidence,
    )
    return StoredDecision(ticket_id=ticket_id, status=status, decision=decision)
