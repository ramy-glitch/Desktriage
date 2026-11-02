# A finished ticket writes one decision containing category, priority,
# confidence, the human-review flag, the destination, and the model version.
# The status read can reconstruct the outcome from that record.

from collections.abc import Mapping
from typing import cast

import pytest

from desktriage_common.enums import Category, Priority
from desktriage_common.statuses import Status
from worker.app.trace import TraceError, record_decision


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
        sql = str(statement)
        self.calls.append((sql, params))
        if "UPDATE tickets" in sql:
            return _Result(self._update_row)
        return _Result(None)


class _Sessions:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, *args: object) -> bool:
        return False


def _patch_store(
    monkeypatch: pytest.MonkeyPatch,
    session: _Session,
) -> None:
    monkeypatch.setattr("worker.app.trace.model_version", lambda: "abc123")
    monkeypatch.setattr(
        "worker.app.trace.get_session",
        lambda: _Sessions(session),
    )


def test_routed_ticket_stores_one_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch_store(monkeypatch, session)

    stored = record_decision(
        " ticket-1 ",
        category=Category.CLAIMS_AND_APPEALS,
        priority=Priority.P2,
        confidence=0.8,
        requires_human_review=False,
        destination="claims_support",
    )

    assert stored.ticket_id == "ticket-1"
    assert stored.status is Status.ROUTED
    assert stored.decision.category is Category.CLAIMS_AND_APPEALS
    assert stored.decision.priority is Priority.P2
    assert stored.decision.confidence == 0.8
    assert stored.decision.requires_human_review is False
    assert stored.decision.destination == "claims_support"
    assert stored.decision.model_version == "abc123"
    update, insert = session.calls
    assert update[1]["status"] == "routed"
    assert update[1]["processing"] == "processing"
    assert insert[1] == {
        "ticket_id": "ticket-1",
        "category": "claims_and_appeals",
        "priority": "P2",
        "confidence": 0.8,
        "requires_human_review": False,
        "destination": "claims_support",
        "routing_outcome": "routed",
        "model_version": "abc123",
    }


def test_human_review_stores_no_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-2"})
    _patch_store(monkeypatch, session)

    stored = record_decision(
        "ticket-2",
        category="other_or_unknown",
        priority="P3",
        confidence=0.2,
        requires_human_review=True,
        destination=None,
    )

    assert stored.status is Status.NEEDS_HUMAN_REVIEW
    assert stored.decision.destination is None
    assert stored.decision.requires_human_review is True
    assert session.calls[1][1]["routing_outcome"] == "needs_human_review"
    assert session.calls[1][1]["destination"] is None


def test_a_ticket_that_is_not_processing_is_not_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session(None)
    _patch_store(monkeypatch, session)

    with pytest.raises(TraceError):
        record_decision(
            "ticket-3",
            category=Category.ACCESS_AND_REFERRALS,
            priority=Priority.P4,
            confidence=0.9,
            requires_human_review=False,
            destination="access_support",
        )

    assert len(session.calls) == 1
    assert "UPDATE tickets" in session.calls[0][0]


def test_review_with_a_destination_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-4"})
    _patch_store(monkeypatch, session)

    with pytest.raises(TraceError):
        record_decision(
            "ticket-4",
            category=Category.POLICY_INTERPRETATION,
            priority=Priority.P1,
            confidence=0.4,
            requires_human_review=True,
            destination="policy_specialist",
        )

    assert session.calls == []


def test_a_blank_ticket_is_not_written(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch_store(monkeypatch, session)

    with pytest.raises(TraceError, match="ticket_id"):
        record_decision(
            " ",
            category=Category.CLAIMS_AND_APPEALS,
            priority=Priority.P3,
            confidence=0.5,
            requires_human_review=False,
            destination="claims_support",
        )

    assert session.calls == []


def test_the_review_flag_must_be_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch_store(monkeypatch, session)

    with pytest.raises(TraceError, match="requires_human_review"):
        record_decision(
            "ticket-1",
            category=Category.CLAIMS_AND_APPEALS,
            priority=Priority.P3,
            confidence=0.5,
            requires_human_review=cast(bool, 1),
            destination="claims_support",
        )

    assert session.calls == []


def test_a_routed_decision_needs_a_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch_store(monkeypatch, session)

    with pytest.raises(TraceError, match="does not match"):
        record_decision(
            "ticket-1",
            category=Category.CLAIMS_AND_APPEALS,
            priority=Priority.P2,
            confidence=0.9,
            requires_human_review=False,
            destination=None,
        )

    assert session.calls == []


def test_confidence_outside_zero_to_one_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session({"ticket_id": "ticket-1"})
    _patch_store(monkeypatch, session)

    with pytest.raises(TraceError, match="does not match"):
        record_decision(
            "ticket-1",
            category=Category.ACCESS_AND_REFERRALS,
            priority=Priority.P4,
            confidence=1.1,
            requires_human_review=False,
            destination="access_support",
        )

    assert session.calls == []
