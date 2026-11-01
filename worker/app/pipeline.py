"""Run one claimed ticket through triage.

The steps stay in their own modules. This module calls them in order:
  1. classifier.predict  -> category and both confidences
  2. priority.policy     -> operational priority
  3. confidence.gate     -> whether either head is safe to route
  4. routing.rules       -> destination team when the gate allows it
     or review.queue     -> human review when the gate withholds routing,
                            or when the category has no team
  5. trace               -> store the decision
  6. notify.webhook      -> tell the receiver the ticket is ready

On an exception, call retry.py and leave the ticket in the database.
A handled failure does not raise again, so the poll loop does not schedule
a second retry for the same attempt.
"""

from desktriage_common.enums import Category, Priority

from worker.app.claim import ClaimedTicket
from worker.app.classifier.predict import predict
from worker.app.confidence.gate import evaluate
from worker.app.priority.policy import assign_priority
from worker.app.review.queue import hold_for_review
from worker.app.retry import schedule_retry
from worker.app.routing.rules import destination_team
from worker.app.trace import StoredDecision, record_decision


def process_ticket(claimed: ClaimedTicket) -> StoredDecision | None:
    """Triage one claimed ticket. Return the stored decision, or None when retry took it."""
    try:
        return _triage(claimed)
    except Exception as exc:
        schedule_retry(claimed, exc)
        return None


def _triage(claimed: ClaimedTicket) -> StoredDecision:
    scored = predict(claimed.query_text, claimed.escalation_reason)
    priority = assign_priority(claimed.query_text, claimed.escalation_reason)
    gate = evaluate(scored.confidence, scored.priority_confidence)
    destination = (
        destination_team(scored.category, priority) if gate.allow_routing else None
    )
    if destination is None:
        review = hold_for_review(scored.category, priority, scored.confidence)
        category: Category = review.category
        priority = review.priority
        confidence = review.confidence
        requires_human_review = True
        destination = review.destination
    else:
        category = scored.category
        confidence = scored.confidence
        requires_human_review = False

    stored = record_decision(
        claimed.ticket_id,
        category=category,
        priority=priority,
        confidence=confidence,
        requires_human_review=requires_human_review,
        destination=destination,
    )
    _notify(stored)
    return stored


def _notify(stored: StoredDecision) -> None:
    from worker.app.notify.webhook import notify

    notify(stored)
