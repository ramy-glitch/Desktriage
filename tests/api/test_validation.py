# An incomplete or malformed intake body is rejected with the error response
# from api/app/errors.py.
# Cover a missing query and a body that is not the ingest schema.

import pytest
from fastapi.testclient import TestClient

from desktriage_common.schemas import TicketIngest


def _reject_if_called(ticket: TicketIngest) -> None:
    raise AssertionError(ticket)


def test_a_missing_query_is_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)
    body = dict(intake_body)
    del body["query_text"]

    response = api_client.post("/tickets", json=body)

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "validation_error"
    assert payload["message"] == "intake body is missing the escalated query"
    assert payload["errors"]
    assert any(item["field"] == "query_text" for item in payload["errors"])
    assert all(set(item) == {"field", "message", "type"} for item in payload["errors"])


@pytest.mark.parametrize("query_text", ["", "   ", None])
def test_a_blank_query_is_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
    query_text: object,
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)
    body = dict(intake_body)
    body["query_text"] = query_text

    response = api_client.post("/tickets", json=body)

    assert response.status_code == 422
    assert response.json()["message"] == "intake body is missing the escalated query"


def test_an_empty_object_is_a_missing_query(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)

    response = api_client.post("/tickets", json={})

    assert response.status_code == 422
    assert response.json()["message"] == "intake body is missing the escalated query"


@pytest.mark.parametrize("field", ["escalation_reason", "user_id"])
def test_a_missing_companion_field_is_malformed(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
    field: str,
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)
    body = dict(intake_body)
    del body[field]

    response = api_client.post("/tickets", json=body)

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "validation_error"
    assert payload["message"] == "intake body is malformed"
    assert any(item["field"] == field for item in payload["errors"])


def test_a_non_string_query_is_malformed(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)
    body = dict(intake_body)
    body["query_text"] = 12

    response = api_client.post("/tickets", json=body)

    assert response.status_code == 422
    assert response.json()["message"] == "intake body is malformed"


def test_category_priority_and_team_are_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    intake_body: dict[str, str],
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)
    secret = "SECRET-CATEGORY-VALUE"
    body = dict(intake_body)
    body["category"] = secret
    body["priority"] = "P1"
    body["assigned_team"] = "claims_support"

    response = api_client.post("/tickets", json=body)

    assert response.status_code == 422
    payload = response.json()
    assert payload["message"] == "intake body is malformed"
    assert any(item["field"] == "category" for item in payload["errors"])
    assert secret not in response.text
    assert "claims_support" not in response.text


def test_a_json_array_is_malformed(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)

    response = api_client.post("/tickets", json=["not", "a", "ticket"])

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "validation_error"
    assert payload["message"] == "intake body is malformed"
    assert payload["errors"] == []


def test_malformed_json_is_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)

    response = api_client.post(
        "/tickets",
        content=b"{",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "validation_error"
    assert payload["message"] == "intake body is malformed"
    assert payload["errors"] == []


def test_an_empty_body_is_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.app.routes.ingest.insert_ticket", _reject_if_called)

    response = api_client.post("/tickets")

    assert response.status_code == 422
    assert response.json()["message"] == "intake body is malformed"
