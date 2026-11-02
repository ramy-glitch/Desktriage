# Shared contracts: intake carries the escalated query only.
# A decision's destination follows the human-review flag.
# A status response carries a decision only once triage has finished.

import pytest
from pydantic import ValidationError

from desktriage_common.enums import Category, Priority
from desktriage_common.schemas import (
    TicketAccepted,
    TicketIngest,
    TicketStatus,
    TriageDecision,
    WebhookNotification,
)
from desktriage_common.statuses import Status


def _fields(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "category": Category.CLAIMS_AND_APPEALS,
        "priority": Priority.P2,
        "confidence": 0.8,
        "requires_human_review": False,
        "destination": "claims_support",
        "model_version": "abc123",
    }
    body.update(overrides)
    return body


def test_intake_keeps_the_stripped_query() -> None:
    ticket = TicketIngest(
        query_text="  When does coverage start? ",
        escalation_reason=" assistant unsure ",
        user_id=" user-1 ",
    )
    assert ticket.query_text == "When does coverage start?"
    assert ticket.escalation_reason == "assistant unsure"
    assert ticket.user_id == "user-1"


def test_a_blank_query_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TicketIngest(query_text="   ", escalation_reason="assistant unsure", user_id="user-1")


def test_intake_rejects_category_priority_and_team() -> None:
    with pytest.raises(ValidationError):
        TicketIngest.model_validate(
            {
                "query_text": "When does coverage start?",
                "escalation_reason": "assistant unsure",
                "user_id": "user-1",
                "category": Category.CLAIMS_AND_APPEALS.value,
                "priority": Priority.P2.value,
                "assigned_team": "claims_support",
            }
        )


def test_a_routed_decision_needs_a_team() -> None:
    decision = TriageDecision(**_fields())
    assert decision.destination == "claims_support"
    with pytest.raises(ValidationError):
        TriageDecision(**_fields(destination=None))


def test_a_review_decision_has_no_team() -> None:
    decision = TriageDecision(
        **_fields(
            category=Category.OTHER_OR_UNKNOWN,
            requires_human_review=True,
            destination=None,
        )
    )
    assert decision.destination is None
    with pytest.raises(ValidationError):
        TriageDecision(
            **_fields(
                requires_human_review=True,
                destination="claims_support",
            )
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_stays_between_zero_and_one(confidence: float) -> None:
    with pytest.raises(ValidationError):
        TriageDecision(**_fields(confidence=confidence))


def test_model_version_and_destination_must_be_present() -> None:
    with pytest.raises(ValidationError):
        TriageDecision(**_fields(model_version="  "))
    with pytest.raises(ValidationError):
        TriageDecision(**_fields(destination="  "))


def test_intake_returns_the_accepted_status() -> None:
    accepted = TicketAccepted(ticket_id=" ticket-1 ")
    assert accepted.ticket_id == "ticket-1"
    assert accepted.status is Status.ACCEPTED
    with pytest.raises(ValidationError):
        TicketAccepted(ticket_id="ticket-1", status=Status.QUEUED)


def test_an_open_ticket_has_no_decision() -> None:
    status = TicketStatus(ticket_id="ticket-1", status=Status.QUEUED)
    assert status.decision is None
    with pytest.raises(ValidationError):
        TicketStatus(
            ticket_id="ticket-1",
            status=Status.QUEUED,
            decision=TriageDecision(**_fields()),
        )


def test_a_finished_status_includes_a_matching_decision() -> None:
    with pytest.raises(ValidationError):
        TicketStatus(ticket_id="ticket-1", status=Status.ROUTED)
    review = TriageDecision(
        **_fields(
            category=Category.OTHER_OR_UNKNOWN,
            requires_human_review=True,
            destination=None,
        )
    )
    with pytest.raises(ValidationError):
        TicketStatus(ticket_id="ticket-1", status=Status.ROUTED, decision=review)
    held = TicketStatus(
        ticket_id="ticket-1",
        status=Status.NEEDS_HUMAN_REVIEW,
        decision=review,
    )
    assert held.decision is review


def test_a_failed_ticket_can_be_read_without_a_decision() -> None:
    status = TicketStatus(ticket_id="ticket-1", status=Status.FAILED)
    assert status.decision is None


def test_a_notification_status_matches_the_decision() -> None:
    decision = TriageDecision(**_fields())
    note = WebhookNotification(
        idempotency_key=" ticket-1:10 ",
        ticket_id=" ticket-1 ",
        status=Status.ROUTED,
        decision=decision,
    )
    assert note.idempotency_key == "ticket-1:10"
    assert note.ticket_id == "ticket-1"
    with pytest.raises(ValidationError):
        WebhookNotification(
            idempotency_key="ticket-1:10",
            ticket_id="ticket-1",
            status=Status.NEEDS_HUMAN_REVIEW,
            decision=decision,
        )


def test_a_notification_needs_an_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        WebhookNotification(
            idempotency_key="  ",
            ticket_id="ticket-1",
            status=Status.ROUTED,
            decision=TriageDecision(**_fields()),
        )
