# POST /notifications stores one body per idempotency key.
# A second POST with the same key succeeds and does not replace the first body.
# A body that is not a WebhookNotification is rejected.

import pytest
from fastapi.testclient import TestClient

from desktriage_common.enums import Category, Priority
from desktriage_common.statuses import Status
from webhook.app.main import create_app
from webhook.app.receipts import clear


@pytest.fixture
def client() -> TestClient:
    clear()
    return TestClient(create_app())


def _body(*, key: str = "ticket-1:10", destination: str | None = "claims_support") -> dict[str, object]:
    review = destination is None
    return {
        "idempotency_key": key,
        "ticket_id": "ticket-1",
        "status": Status.NEEDS_HUMAN_REVIEW.value if review else Status.ROUTED.value,
        "decision": {
            "category": Category.OTHER_OR_UNKNOWN.value if review else Category.CLAIMS_AND_APPEALS.value,
            "priority": Priority.P3.value if review else Priority.P2.value,
            "confidence": 0.2 if review else 0.9,
            "requires_human_review": review,
            "destination": destination,
            "model_version": "abc123",
        },
    }


def test_a_new_notification_is_stored(client: TestClient) -> None:
    response = client.post("/notifications", json=_body())

    assert response.status_code == 200
    assert response.json() == {
        "idempotency_key": "ticket-1:10",
        "ticket_id": "ticket-1",
        "duplicate": False,
    }


def test_a_repeated_key_is_a_duplicate_and_keeps_the_first_body(client: TestClient) -> None:
    from webhook.app.receipts import lookup

    first = client.post(
        "/notifications",
        json=_body(destination="claims_support"),
        headers={"Idempotency-Key": "ticket-1:10"},
    )
    second = client.post(
        "/notifications",
        json=_body(destination="access_support"),
        headers={"Idempotency-Key": "ticket-1:10"},
    )

    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    stored = lookup("ticket-1:10")
    assert stored is not None
    assert stored.decision.destination == "claims_support"


def test_a_human_review_notification_is_accepted(client: TestClient) -> None:
    response = client.post("/notifications", json=_body(key="ticket-1:11", destination=None))

    assert response.status_code == 200
    assert response.json()["duplicate"] is False


def test_a_header_that_does_not_match_the_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=_body(),
        headers={"Idempotency-Key": "ticket-1:99"},
    )

    assert response.status_code == 400


def test_a_malformed_notification_is_rejected(client: TestClient) -> None:
    response = client.post("/notifications", json={"ticket_id": "ticket-1"})

    assert response.status_code == 422


def test_a_status_that_does_not_match_the_decision_is_rejected(client: TestClient) -> None:
    body = _body()
    body["status"] = Status.NEEDS_HUMAN_REVIEW.value

    response = client.post("/notifications", json=body)

    assert response.status_code == 422


def test_a_review_decision_with_a_team_is_rejected(client: TestClient) -> None:
    body = _body(destination=None)
    body["decision"]["destination"] = "claims_support"
    body["decision"]["requires_human_review"] = True

    response = client.post("/notifications", json=body)

    assert response.status_code == 422


def test_a_header_with_surrounding_space_matches(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=_body(),
        headers={"Idempotency-Key": "  ticket-1:10  "},
    )

    assert response.status_code == 200
    assert response.json()["duplicate"] is False
