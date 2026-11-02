# claim_ticket takes one queued row with FOR UPDATE SKIP LOCKED.
# The returned attempt is the count stored by that update.
# The claim log names the ticket and the attempt, and leaves the query out.

from collections.abc import Mapping

import pytest

from worker.app.claim import claim_ticket


class _Result:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> "_Result":
        return self

    def one_or_none(self) -> Mapping[str, object] | None:
        return self._row


class _Session:
    def __init__(
        self,
        row: Mapping[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[str, Mapping[str, object]]] = []
        self._row = row
        self._error = error
        self.committed = False
        self.rolled_back = False

    def execute(self, statement: object, params: Mapping[str, object]) -> _Result:
        self.calls.append((str(statement), params))
        if self._error is not None:
            raise self._error
        return _Result(self._row)


class _Sessions:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, exc_type: object, *args: object) -> bool:
        if exc_type is None:
            self.session.committed = True
        else:
            self.session.rolled_back = True
        return False


class _Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message: str, *args: object) -> None:
        self.lines.append(message % args)

    def error(self, message: str, *args: object) -> None:
        self.lines.append(message % args)


def _install(monkeypatch: pytest.MonkeyPatch, session: _Session, log: _Log | None = None) -> _Log:
    monkeypatch.setattr("worker.app.claim.get_session", lambda: _Sessions(session))
    recorder = log or _Log()
    monkeypatch.setattr("worker.app.claim.logger", recorder)
    return recorder


def test_an_empty_queue_claims_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session(None)
    _install(monkeypatch, session)

    assert claim_ticket() is None

    sql, params = session.calls[0]
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "ORDER BY next_attempt_at, created_at" in sql
    assert "attempt_count = attempt_count + 1" in sql
    assert params == {"queued": "queued", "processing": "processing"}
    assert session.committed is True


def test_a_claim_returns_the_stored_attempt_and_hides_the_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session(
        {
            "ticket_id": "ticket-1",
            "user_id": "user-1",
            "query_text": "secret appeal wording",
            "escalation_reason": "human_requested",
            "attempt_count": 2,
        }
    )
    log = _install(monkeypatch, session)

    claimed = claim_ticket()

    assert claimed is not None
    assert claimed.ticket_id == "ticket-1"
    assert claimed.user_id == "user-1"
    assert claimed.query_text == "secret appeal wording"
    assert claimed.escalation_reason == "human_requested"
    assert claimed.attempt == 2
    assert log.lines == ["event=ticket_claimed ticket_id=ticket-1 attempt=2"]
    assert session.committed is True


def test_a_database_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session(error=ConnectionError("database unavailable"))
    _install(monkeypatch, session)

    with pytest.raises(ConnectionError):
        claim_ticket()

    assert session.rolled_back is True
    assert session.committed is False
