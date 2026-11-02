# Fixtures shared by the tests.
# Build a valid escalated ticket (query text and escalation reason) and the
# database or client objects each test needs.
# Category and priority under test come from the worker or from a fixture decision,
# not from fields posted to the intake API.

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def intake_body() -> dict[str, str]:
    """Escalated query the assistant is allowed to submit."""
    return {
        "query_text": "When does coverage start?",
        "escalation_reason": "assistant unsure",
        "user_id": "user-1",
    }


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Intake API with startup pointed at a stand-in for PostgreSQL.

    Route tests replace insert_ticket or get_ticket when they need a row.
    """
    monkeypatch.setattr("api.app.main.get_settings", lambda: object())
    monkeypatch.setattr("api.app.main.check_session", lambda: None)
    from api.app.main import create_app

    with TestClient(create_app()) as client:
        yield client
