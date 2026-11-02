# A valid ticket posted to the intake route receives a structured response
# with a ticket id and the accepted status.
# The response does not include a category or a team. Those arrive on the status
# route after the worker has stored a decision.

import uuid

import pytest
from fastapi.testclient import TestClient

from desktriage_common.schemas import TicketAccepted, TicketIngest


def _accept(ticket: TicketIngest) -> TicketAccepted:
    return TicketAccepted(ticket_id=str(uuid.uuid4()))


def test_a_valid_ticket_is_accepted(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _accept)

    response = api_client.post("/tickets", json=intake_body)

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"ticket_id", "status"}
    assert body["status"] == "accepted"
    uuid.UUID(body["ticket_id"])


def test_each_ticket_receives_its_own_id(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _accept)

    first = api_client.post("/tickets", json=intake_body)
    second = api_client.post("/tickets", json=intake_body)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["ticket_id"] != second.json()["ticket_id"]


def test_intake_stores_the_stripped_query(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[TicketIngest] = []

    def insert(ticket: TicketIngest) -> TicketAccepted:
        seen.append(ticket)
        return TicketAccepted(ticket_id="ticket-1")

    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", insert)
    response = api_client.post(
        "/tickets",
        json={
            "query_text": "  When does coverage start?  ",
            "escalation_reason": "  assistant unsure ",
            "user_id": " user-1 ",
        },
    )

    assert response.status_code == 202
    assert seen[0].query_text == "When does coverage start?"
    assert seen[0].escalation_reason == "assistant unsure"
    assert seen[0].user_id == "user-1"
    assert set(response.json()) == {"ticket_id", "status"}
