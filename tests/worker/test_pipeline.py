# The pipeline runs classification, priority, the confidence gate, then either
# human review or routing, then the decision write and the notification.
# A low-confidence ticket ends in review and is not given an automatic team.
# A high-confidence ticket ends routed to the configured team.

import pytest

from desktriage_common.enums import Category, Priority
from desktriage_common.schemas import TriageDecision
from desktriage_common.statuses import Status
from worker.app.claim import ClaimedTicket
from worker.app.classifier.predict import Classification
from worker.app.pipeline import process_ticket
from worker.app.trace import StoredDecision


def _ticket() -> ClaimedTicket:
    return ClaimedTicket(
        ticket_id="ticket-1",
        user_id="user-1",
        query_text="where is my claim",
        escalation_reason="conflicting_evidence",
        attempt=1,
    )


def _scored(
    category: Category,
    confidence: float,
    priority_confidence: float,
) -> Classification:
    return Classification(
        category=category,
        confidence=confidence,
        priority=Priority.P1,
        priority_confidence=priority_confidence,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    scored: Classification,
    priority: Priority,
) -> dict[str, list[object]]:
    seen: dict[str, list[object]] = {
        "teams": [],
        "stored": [],
        "notified": [],
        "retried": [],
    }

    def record(ticket_id: str, **kwargs: object) -> StoredDecision:
        seen["stored"].append((ticket_id, kwargs))
        decision = TriageDecision(model_version="abc123", **kwargs)
        status = (
            Status.NEEDS_HUMAN_REVIEW
            if decision.requires_human_review
            else Status.ROUTED
        )
        return StoredDecision(ticket_id=ticket_id, status=status, decision=decision)

    monkeypatch.setattr("worker.app.pipeline.predict", lambda query_text, escalation_reason: scored)
    monkeypatch.setattr(
        "worker.app.pipeline.assign_priority",
        lambda query_text, escalation_reason: priority,
    )
    monkeypatch.setattr(
        "worker.app.pipeline.destination_team",
        lambda category, priority: seen["teams"].append((category, priority)) or _team(category),
    )
    monkeypatch.setattr("worker.app.pipeline.record_decision", record)
    monkeypatch.setattr("worker.app.pipeline._notify", lambda stored: seen["notified"].append(stored))
    monkeypatch.setattr(
        "worker.app.pipeline.schedule_retry",
        lambda claimed, exc: seen["retried"].append((claimed, exc)),
    )
    return seen


def _team(category: Category) -> str | None:
    if category is Category.OTHER_OR_UNKNOWN:
        return None
    return "claims_support"


def test_low_confidence_ends_in_review_without_a_team(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _install(
        monkeypatch,
        _scored(Category.CLAIMS_AND_APPEALS, 0.29, 0.29),
        Priority.P3,
    )

    stored = process_ticket(_ticket())

    assert stored is not None
    assert stored.status is Status.NEEDS_HUMAN_REVIEW
    assert stored.decision.requires_human_review is True
    assert stored.decision.destination is None
    assert stored.decision.priority is Priority.P3
    assert stored.decision.confidence == 0.29
    assert seen["teams"] == []
    assert seen["notified"] == [stored]
    assert seen["retried"] == []


def test_high_confidence_routes_to_the_configured_team(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _install(
        monkeypatch,
        _scored(Category.CLAIMS_AND_APPEALS, 0.90, 0.90),
        Priority.P2,
    )

    stored = process_ticket(_ticket())

    assert stored is not None
    assert stored.status is Status.ROUTED
    assert stored.decision.requires_human_review is False
    assert stored.decision.destination == "claims_support"
    assert stored.decision.category is Category.CLAIMS_AND_APPEALS
    assert stored.decision.priority is Priority.P2
    assert seen["teams"] == [(Category.CLAIMS_AND_APPEALS, Priority.P2)]
    assert seen["notified"] == [stored]


def test_one_confident_head_is_enough_to_route(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _install(
        monkeypatch,
        _scored(Category.CLAIMS_AND_APPEALS, 0.90, 0.10),
        Priority.P3,
    )

    stored = process_ticket(_ticket())

    assert stored is not None
    assert stored.decision.destination == "claims_support"
    assert seen["teams"] == [(Category.CLAIMS_AND_APPEALS, Priority.P3)]


def test_a_review_category_has_no_team_when_the_gate_allows_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _scored(Category.OTHER_OR_UNKNOWN, 0.90, 0.90),
        Priority.P1,
    )

    stored = process_ticket(_ticket())

    assert stored is not None
    assert stored.status is Status.NEEDS_HUMAN_REVIEW
    assert stored.decision.destination is None
    assert stored.decision.category is Category.OTHER_OR_UNKNOWN


def test_a_failure_is_handed_to_retry_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _install(
        monkeypatch,
        _scored(Category.CLAIMS_AND_APPEALS, 0.90, 0.90),
        Priority.P2,
    )
    failure = RuntimeError("classifier unavailable")

    def fail(query_text: str, escalation_reason: str) -> Classification:
        raise failure

    monkeypatch.setattr("worker.app.pipeline.predict", fail)

    ticket = _ticket()
    assert process_ticket(ticket) is None
    assert seen["stored"] == []
    assert seen["notified"] == []
    assert seen["retried"] == [(ticket, failure)]
