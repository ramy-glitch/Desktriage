# Intake failures return a meaningful error and do not leave an unrecorded ticket
# that the worker could silently skip.
# A ticket that was stored and later fails in the worker stays readable, with a
# failed or retrying status, rather than disappearing from the status route.

from collections.abc import Mapping

import pytest
from fastapi.testclient import TestClient

from api.app.errors import TicketStoreError, intake_error_response
from api.app.repository import insert_ticket
from desktriage_common.schemas import TicketAccepted, TicketIngest, TicketStatus
from desktriage_common.statuses import Status


class _Session:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.committed = False
        self.rolled_back = False

    def execute(self, statement: object, params: Mapping[str, object]) -> None:
        raise self.error

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class _Sessions:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        return False


def test_a_storage_failure_has_no_ticket_id(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    query = intake_body["query_text"]

    def insert(ticket: TicketIngest) -> TicketAccepted:
        raise TicketStoreError("the ticket was not stored") from RuntimeError(query)

    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", insert)

    response = api_client.post("/tickets", json=intake_body)

    assert response.status_code == 500
    assert response.json() == {
        "error": "storage_error",
        "message": "the ticket was not stored",
    }
    assert "ticket_id" not in response.json()
    assert query not in response.text


def test_a_failed_insert_rolls_back_and_returns_no_id(
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    session = _Session(RuntimeError(intake_body["query_text"]))
    monkeypatch.setattr("api.app.repository.get_session", lambda: _Sessions(session))

    with pytest.raises(TicketStoreError, match="the ticket was not stored") as caught:
        insert_ticket(TicketIngest.model_validate(intake_body))

    assert intake_body["query_text"] not in str(caught.value)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert session.rolled_back is True
    assert session.committed is False


def test_intake_error_response_rejects_a_later_processing_failure() -> None:
    with pytest.raises(TypeError):
        intake_error_response(RuntimeError("the worker failed after the row was stored"))


def test_a_failed_ticket_stays_on_the_status_route(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "api.app.routes.status.get_ticket",
        lambda ticket_id: TicketStatus(ticket_id=ticket_id, status=Status.FAILED),
    )

    response = api_client.get("/tickets/ticket-1")

    assert response.status_code == 200
    assert response.json() == {
        "ticket_id": "ticket-1",
        "status": "failed",
        "decision": None,
    }


def test_a_ticket_waiting_to_be_retried_stays_readable(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "api.app.routes.status.get_ticket",
        lambda ticket_id: TicketStatus(ticket_id=ticket_id, status=Status.QUEUED),
    )

    response = api_client.get("/tickets/ticket-1")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["decision"] is None
