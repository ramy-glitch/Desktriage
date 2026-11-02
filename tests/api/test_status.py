# The status route returns the ticket id and the lifecycle status.
# Before the worker finishes, the decision fields are empty.
# After a stored decision, the response includes category, priority, confidence,
# the human-review flag, and the destination when one was assigned.
# An unknown id returns a not-found error.

import pytest
from fastapi.testclient import TestClient

from desktriage_common.enums import Category, Priority
from desktriage_common.schemas import TicketStatus, TriageDecision
from desktriage_common.statuses import Status


def _decision(*, review: bool) -> TriageDecision:
    return TriageDecision(
        category=Category.OTHER_OR_UNKNOWN if review else Category.CLAIMS_AND_APPEALS,
        priority=Priority.P3 if review else Priority.P2,
        confidence=0.2 if review else 0.9,
        requires_human_review=review,
        destination=None if review else "claims_support",
        model_version="abc123",
    )


@pytest.mark.parametrize("status", [Status.QUEUED, Status.PROCESSING])
def test_an_unfinished_ticket_has_no_decision(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    status: Status,
) -> None:
    monkeypatch.setattr(
        "api.app.routes.status.get_ticket",
        lambda ticket_id: TicketStatus(ticket_id=ticket_id, status=status),
    )

    response = api_client.get("/tickets/ticket-1")

    assert response.status_code == 200
    assert response.json() == {
        "ticket_id": "ticket-1",
        "status": status.value,
        "decision": None,
    }
    assert "query_text" not in response.text


def test_a_routed_ticket_includes_the_decision(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "api.app.routes.status.get_ticket",
        lambda ticket_id: TicketStatus(
            ticket_id=ticket_id,
            status=Status.ROUTED,
            decision=_decision(review=False),
        ),
    )

    response = api_client.get("/tickets/ticket-1")

    assert response.status_code == 200
    assert response.json() == {
        "ticket_id": "ticket-1",
        "status": "routed",
        "decision": {
            "category": "claims_and_appeals",
            "priority": "P2",
            "confidence": 0.9,
            "requires_human_review": False,
            "destination": "claims_support",
            "model_version": "abc123",
        },
    }


def test_a_human_review_ticket_has_no_destination(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "api.app.routes.status.get_ticket",
        lambda ticket_id: TicketStatus(
            ticket_id=ticket_id,
            status=Status.NEEDS_HUMAN_REVIEW,
            decision=_decision(review=True),
        ),
    )

    response = api_client.get("/tickets/ticket-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_human_review"
    assert body["decision"]["requires_human_review"] is True
    assert body["decision"]["destination"] is None
    assert body["decision"]["category"] == "other_or_unknown"
    assert body["decision"]["priority"] == "P3"
    assert body["decision"]["confidence"] == 0.2


def test_an_unknown_id_is_not_found(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.app.routes.status.get_ticket", lambda ticket_id: None)

    response = api_client.get("/tickets/missing-id")

    assert response.status_code == 404
    assert response.json() == {
        "error": "not_found",
        "message": "ticket not found",
        "ticket_id": "missing-id",
    }


def test_the_status_route_reads_the_path_id(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def get_ticket(ticket_id: str) -> TicketStatus:
        seen.append(ticket_id)
        return TicketStatus(ticket_id=ticket_id, status=Status.QUEUED)

    monkeypatch.setattr("api.app.routes.status.get_ticket", get_ticket)

    response = api_client.get("/tickets/ticket-42")

    assert response.status_code == 200
    assert seen == ["ticket-42"]
