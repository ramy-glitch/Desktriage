# The loop claims one ticket, hands it to the pipeline, then waits.
# An empty queue waits and claims again. A failed ticket stays recorded
# and is passed to retry.

from worker.app.claim import ClaimedTicket
from worker.app.loop import run


def _ticket() -> ClaimedTicket:
    return ClaimedTicket(
        ticket_id="ticket-1",
        user_id="user-1",
        query_text="where is my claim",
        escalation_reason="conflicting_evidence",
        attempt=1,
    )


def test_empty_queue_waits_and_claims_again(monkeypatch) -> None:
    claims = {"count": 0}
    processed: list[ClaimedTicket] = []
    waits: list[float] = []

    def claim() -> None:
        claims["count"] += 1
        return None

    monkeypatch.setattr("worker.app.loop.claim_ticket", claim)
    monkeypatch.setattr("worker.app.loop._process_ticket", lambda claimed: processed.append(claimed))
    monkeypatch.setattr("worker.app.loop.sleep", waits.append)

    run(poll_interval=0.5, stop=lambda: claims["count"] >= 2)

    assert claims["count"] == 2
    assert processed == []
    assert waits == [0.5]


def test_claimed_ticket_is_passed_to_the_pipeline(monkeypatch) -> None:
    ticket = _ticket()
    claims = {"count": 0}
    processed: list[ClaimedTicket] = []
    retried: list[ClaimedTicket] = []

    def claim() -> ClaimedTicket | None:
        claims["count"] += 1
        if claims["count"] == 1:
            return ticket
        return None

    monkeypatch.setattr("worker.app.loop.claim_ticket", claim)
    monkeypatch.setattr("worker.app.loop._process_ticket", lambda claimed: processed.append(claimed))
    monkeypatch.setattr(
        "worker.app.loop._schedule_retry",
        lambda claimed, exc: retried.append(claimed),
    )
    monkeypatch.setattr("worker.app.loop.sleep", lambda seconds: None)

    run(stop=lambda: claims["count"] >= 2)

    assert processed == [ticket]
    assert retried == []


def test_a_failed_ticket_is_left_for_retry(monkeypatch) -> None:
    ticket = _ticket()
    claims = {"count": 0}
    retried: list[tuple[ClaimedTicket, Exception]] = []
    failure = RuntimeError("classifier unavailable")

    def claim() -> ClaimedTicket | None:
        claims["count"] += 1
        if claims["count"] == 1:
            return ticket
        return None

    def process(claimed: ClaimedTicket) -> None:
        raise failure

    monkeypatch.setattr("worker.app.loop.claim_ticket", claim)
    monkeypatch.setattr("worker.app.loop._process_ticket", process)
    monkeypatch.setattr(
        "worker.app.loop._schedule_retry",
        lambda claimed, exc: retried.append((claimed, exc)),
    )
    monkeypatch.setattr("worker.app.loop.sleep", lambda seconds: None)

    run(stop=lambda: claims["count"] >= 2)

    assert retried == [(ticket, failure)]


def test_a_claim_failure_does_not_call_retry(monkeypatch) -> None:
    claims = {"count": 0}
    retried: list[ClaimedTicket] = []

    def claim() -> None:
        claims["count"] += 1
        raise ConnectionError("database unavailable")

    monkeypatch.setattr("worker.app.loop.claim_ticket", claim)
    monkeypatch.setattr(
        "worker.app.loop._schedule_retry",
        lambda claimed, exc: retried.append(claimed),
    )
    monkeypatch.setattr("worker.app.loop.sleep", lambda seconds: None)

    run(poll_interval=1, stop=lambda: claims["count"] >= 1)

    assert retried == []
