# End-to-end check across the Compose services.
# Submit a valid ticket to the API and read it back by id.
# After the worker runs, the status includes the decision, and the webhook
# receiver has one logical notification for that decision.
# Also run one ticket that falls below the confidence threshold and confirm
# the status is human review and no destination team was assigned.
# Invalid bodies are covered in tests/api and can stay out of this stack test.
#
# Skipped unless DESKTRIAGE_E2E=1. The API defaults to http://127.0.0.1:8000.
# Set DESKTRIAGE_API_URL when intake is published on another address.
# Set DESKTRIAGE_DATABASE_URL to a URL this process can open, using 127.0.0.1
# rather than the Compose host name db, to check webhook_deliveries.

import os
import time
from collections.abc import Iterator, Mapping

import httpx
import pytest
from sqlalchemy import create_engine, text

from desktriage_common.enums import Category, Priority
from worker.app.routing.rules import destination_team

pytestmark = pytest.mark.integration

DECISION_TIMEOUT_SECONDS = 30.0

_CLAIMS = {
    "query_text": (
        "The guidance about the submission deadline for my appeal is ambiguous. "
        "I need clarification before a documented deadline next week."
    ),
    "escalation_reason": "human_requested",
    "user_id": "user-1",
}
_OUT_OF_SCOPE = {
    "query_text": (
        "I have a policy-related question, but the available categories do not "
        "seem to describe it. I would appreciate clarification during the normal "
        "support process."
    ),
    "escalation_reason": "out_of_scope",
    "user_id": "user-2",
}


@pytest.fixture
def api() -> Iterator[httpx.Client]:
    if os.environ.get("DESKTRIAGE_E2E") != "1":
        pytest.skip("Set DESKTRIAGE_E2E=1 to run against the Compose services")
    base = os.environ.get("DESKTRIAGE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    with httpx.Client(base_url=base, timeout=10) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        assert health.json() == {"status": "ok", "database": "ok"}
        yield client


def _submit(api: httpx.Client, body: Mapping[str, str]) -> str:
    response = api.post("/tickets", json=body)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert set(accepted) == {"ticket_id", "status"}
    assert accepted["status"] == "accepted"
    return str(accepted["ticket_id"])


def _read_while_open(api: httpx.Client, ticket_id: str) -> None:
    response = api.get(f"/tickets/{ticket_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ticket_id"] == ticket_id
    if body["status"] in {"queued", "processing"}:
        assert body["decision"] is None


def _wait(api: httpx.Client, ticket_id: str) -> dict[str, object]:
    deadline = time.monotonic() + DECISION_TIMEOUT_SECONDS
    while True:
        response = api.get(f"/tickets/{ticket_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        status = body["status"]
        if status == "failed":
            pytest.fail(f"ticket {ticket_id} failed: {body}")
        if status in {"routed", "needs_human_review"}:
            return body
        if time.monotonic() >= deadline:
            pytest.fail(f"ticket {ticket_id} stayed {status}: {body}")
        time.sleep(0.5)


def _assert_decision_shape(decision: Mapping[str, object]) -> None:
    assert decision["category"] in {item.value for item in Category}
    assert decision["priority"] in {item.value for item in Priority}
    confidence = decision["confidence"]
    assert isinstance(confidence, (int, float)) and 0.0 <= float(confidence) <= 1.0
    assert isinstance(decision["model_version"], str) and decision["model_version"].strip()


def _assert_one_delivery(ticket_id: str) -> None:
    """One successful webhook_deliveries row, when a host database URL is set."""
    url = os.environ.get("DESKTRIAGE_DATABASE_URL", "").strip()
    if not url:
        return
    engine = create_engine(url)
    statement = text(
        """
        SELECT idempotency_key, response_status
        FROM webhook_deliveries
        WHERE ticket_id = :ticket_id
        ORDER BY id
        """
    )
    try:
        deadline = time.monotonic() + DECISION_TIMEOUT_SECONDS
        rows: list[Mapping[str, object]] = []
        while True:
            with engine.connect() as connection:
                rows = list(connection.execute(statement, {"ticket_id": ticket_id}).mappings())
            if (
                len(rows) == 1
                and isinstance(rows[0]["response_status"], int)
                and 200 <= int(rows[0]["response_status"]) <= 299
            ):
                break
            if time.monotonic() >= deadline:
                pytest.fail(f"webhook delivery for {ticket_id}: {rows}")
            time.sleep(0.5)
    finally:
        engine.dispose()
    assert str(rows[0]["idempotency_key"]).startswith(f"{ticket_id}:")


def test_a_claims_ticket_is_routed_and_notified(api: httpx.Client) -> None:
    ticket_id = _submit(api, _CLAIMS)
    _read_while_open(api, ticket_id)
    finished = _wait(api, ticket_id)

    assert finished["status"] == "routed"
    decision = finished["decision"]
    assert isinstance(decision, dict)
    _assert_decision_shape(decision)
    assert decision["requires_human_review"] is False
    assert decision["destination"] == destination_team(
        str(decision["category"]),
        str(decision["priority"]),
    )
    assert isinstance(decision["destination"], str) and decision["destination"].strip()
    _assert_one_delivery(ticket_id)


def test_an_out_of_scope_ticket_needs_human_review(api: httpx.Client) -> None:
    ticket_id = _submit(api, _OUT_OF_SCOPE)
    _read_while_open(api, ticket_id)
    finished = _wait(api, ticket_id)

    assert finished["status"] == "needs_human_review"
    decision = finished["decision"]
    assert isinstance(decision, dict)
    _assert_decision_shape(decision)
    assert decision["requires_human_review"] is True
    assert decision["destination"] is None
    _assert_one_delivery(ticket_id)
