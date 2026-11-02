# insert_ticket stores a queued row and returns the accepted status.
# get_ticket returns a decision only after the worker has finished.
# Queued, processing, and failed rows stay readable with an empty decision,
# even when a joined decision row is present.

import uuid
from collections.abc import Mapping

import pytest

from api.app.repository import get_ticket, insert_ticket
from desktriage_common.schemas import TicketIngest
from desktriage_common.statuses import Status


class _Result:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> "_Result":
        return self

    def one_or_none(self) -> Mapping[str, object] | None:
        return self._row


class _Session:
    def __init__(self, row: Mapping[str, object] | None = None) -> None:
        self.calls: list[tuple[str, Mapping[str, object]]] = []
        self._row = row

    def execute(self, statement: object, params: Mapping[str, object]) -> _Result:
        self.calls.append((str(statement), params))
        return _Result(self._row)


class _Sessions:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, *args: object) -> bool:
        return False


def _install(monkeypatch: pytest.MonkeyPatch, session: _Session) -> None:
    monkeypatch.setattr("api.app.repository.get_session", lambda: _Sessions(session))


def _ticket() -> TicketIngest:
    return TicketIngest(
        query_text="When does coverage start?",
        escalation_reason="assistant unsure",
        user_id="user-1",
    )


def _row(status: str, **decision: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ticket_id": "ticket-1",
        "status": status,
        "category": "claims_and_appeals",
        "priority": "P1",
        "confidence": 0.95,
        "requires_human_review": False,
        "destination": "claims_support",
        "model_version": "abc123",
    }
    base.update(decision)
    return base


def test_insert_queues_the_row_and_returns_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session()
    _install(monkeypatch, session)

    first = insert_ticket(_ticket())
    second = insert_ticket(_ticket())

    assert first.status is Status.ACCEPTED
    assert first.ticket_id != second.ticket_id
    uuid.UUID(first.ticket_id)
    sql, params = session.calls[0]
    assert "INSERT INTO tickets" in sql
    assert "category" not in sql.lower()
    assert "priority" not in sql.lower()
    assert params == {
        "ticket_id": first.ticket_id,
        "user_id": "user-1",
        "query_text": "When does coverage start?",
        "escalation_reason": "assistant unsure",
        "status": "queued",
    }


def test_an_unknown_id_reads_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session(None)
    _install(monkeypatch, session)

    assert get_ticket("missing") is None
    assert session.calls[0][1] == {"ticket_id": "missing"}


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_an_unfinished_row_ignores_a_joined_decision(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    _install(monkeypatch, _Session(_row(status)))

    found = get_ticket("ticket-1")

    assert found is not None
    assert found.status is Status(status)
    assert found.decision is None


def test_a_routed_row_includes_the_latest_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _Session(_row("routed")))

    found = get_ticket("ticket-1")

    assert found is not None
    assert found.status is Status.ROUTED
    assert found.decision is not None
    assert found.decision.category.value == "claims_and_appeals"
    assert found.decision.priority.value == "P1"
    assert found.decision.confidence == 0.95
    assert found.decision.requires_human_review is False
    assert found.decision.destination == "claims_support"
    assert found.decision.model_version == "abc123"


def test_a_human_review_row_has_no_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _Session(
            _row(
                "needs_human_review",
                category="other_or_unknown",
                priority="P3",
                confidence=0.2,
                requires_human_review=True,
                destination=None,
            )
        ),
    )

    found = get_ticket("ticket-1")

    assert found is not None
    assert found.status is Status.NEEDS_HUMAN_REVIEW
    assert found.decision is not None
    assert found.decision.requires_human_review is True
    assert found.decision.destination is None
