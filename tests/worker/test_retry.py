# A processing failure keeps the ticket row. Claim already counted the attempt,
# so retry leaves that count and schedules another claim.
# Past the attempt limit, the status becomes failed and the ticket remains readable.

from collections.abc import Mapping

import pytest

from desktriage_common.statuses import Status
from worker.app.claim import ClaimedTicket
from worker.app.retry import ATTEMPT_LIMIT, RETRY_BACKOFF_SECONDS, RetryError, schedule_retry


class _Result:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> "_Result":
        return self

    def one_or_none(self) -> Mapping[str, object] | None:
        return self._row


class _Session:
    def __init__(self, update_row: Mapping[str, object] | None) -> None:
        self.calls: list[tuple[str, Mapping[str, object]]] = []
        self._update_row = update_row

    def execute(self, statement: object, params: Mapping[str, object]) -> _Result:
        self.calls.append((str(statement), params))
        return _Result(self._update_row)


class _Sessions:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, *args: object) -> bool:
        return False


def _ticket(attempt: int) -> ClaimedTicket:
    return ClaimedTicket(
        ticket_id=" ticket-1 ",
        user_id="user-1",
        query_text="where is my claim",
        escalation_reason="conflicting_evidence",
        attempt=attempt,
    )


def _patch(monkeypatch: pytest.MonkeyPatch, session: _Session) -> None:
    monkeypatch.setattr("worker.app.retry.get_session", lambda: _Sessions(session))


def test_the_attempt_limit_is_three() -> None:
    assert ATTEMPT_LIMIT == 3


def test_a_failed_attempt_is_requeued_without_counting_it_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)

    plan = schedule_retry(_ticket(1), RuntimeError("classifier unavailable"))

    assert plan.ticket_id == "ticket-1"
    assert plan.attempt == 1
    assert plan.status is Status.QUEUED
    assert plan.delay_seconds == RETRY_BACKOFF_SECONDS
    sql, params = session.calls[0]
    assert "UPDATE tickets" in sql
    assert "DELETE" not in sql
    assert "attempt_count" not in sql
    assert params["status"] == "queued"
    assert params["delay_seconds"] == RETRY_BACKOFF_SECONDS
    assert params["processing"] == "processing"
    assert params["routed"] == "routed"
    assert params["needs_human_review"] == "needs_human_review"


def test_the_second_attempt_waits_longer(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)

    plan = schedule_retry(_ticket(2), TimeoutError("webhook timed out"))

    assert plan.status is Status.QUEUED
    assert plan.delay_seconds == RETRY_BACKOFF_SECONDS * 2


def test_the_third_attempt_marks_the_ticket_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)

    plan = schedule_retry(_ticket(3), ConnectionError("database unavailable"))

    assert plan.status is Status.FAILED
    assert plan.delay_seconds is None
    sql, params = session.calls[0]
    assert "UPDATE tickets" in sql
    assert "next_attempt_at = NULL" in sql
    assert "DELETE" not in sql
    assert params["status"] == "failed"


def test_a_missing_ticket_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session(None)
    _patch(monkeypatch, session)

    with pytest.raises(RetryError):
        schedule_retry(_ticket(1), RuntimeError("classifier unavailable"))


def test_a_blank_ticket_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)
    ticket = ClaimedTicket(
        ticket_id=" ",
        user_id="user-1",
        query_text="where is my claim",
        escalation_reason="conflicting_evidence",
        attempt=1,
    )

    with pytest.raises(RetryError, match="ticket_id"):
        schedule_retry(ticket, RuntimeError("classifier unavailable"))

    assert session.calls == []


def test_attempt_must_be_a_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)

    for attempt in (0, -1, True):
        with pytest.raises(RetryError, match="attempt"):
            schedule_retry(_ticket(attempt), RuntimeError("classifier unavailable"))

    assert session.calls == []


def test_retry_needs_an_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)

    with pytest.raises(RetryError, match="failure"):
        schedule_retry(_ticket(1), BaseException("stop"))

    assert session.calls == []


def test_an_attempt_past_the_limit_marks_the_ticket_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch(monkeypatch, session)

    plan = schedule_retry(_ticket(4), RuntimeError("classifier unavailable"))

    assert plan.status is Status.FAILED
    assert plan.attempt == 4
    assert plan.delay_seconds is None
    assert session.calls[0][1]["status"] == "failed"
