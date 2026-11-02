# remember stores the first body for an idempotency key.
# A later call with that key is a duplicate and leaves the first body in place.
# clear drops the store so the next delivery is new again.

from threading import Thread

from desktriage_common.enums import Category, Priority
from desktriage_common.schemas import TriageDecision, WebhookNotification
from desktriage_common.statuses import Status
from webhook.app.receipts import clear, lookup, remember


def _notification(key: str, ticket_id: str) -> WebhookNotification:
    review = ticket_id.endswith("-review")
    return WebhookNotification(
        idempotency_key=key,
        ticket_id=ticket_id,
        status=Status.NEEDS_HUMAN_REVIEW if review else Status.ROUTED,
        decision=TriageDecision(
            category=Category.OTHER_OR_UNKNOWN if review else Category.CLAIMS_AND_APPEALS,
            priority=Priority.P3 if review else Priority.P2,
            confidence=0.2 if review else 0.9,
            requires_human_review=review,
            destination=None if review else "claims_support",
            model_version="abc123",
        ),
    )


def test_a_repeat_keeps_the_first_body() -> None:
    clear()
    first = _notification("ticket-1:10", "ticket-1")
    second = _notification("ticket-1:10", "ticket-9")

    assert remember(first).duplicate is False
    assert remember(second).duplicate is True
    stored = lookup("ticket-1:10")
    assert stored is not None
    assert stored.ticket_id == "ticket-1"
    assert lookup("missing") is None

    clear()
    assert lookup("ticket-1:10") is None


def test_distinct_keys_are_stored_separately() -> None:
    clear()
    routed = _notification("ticket-1:10", "ticket-1")
    review = _notification("ticket-2:11", "ticket-2-review")

    assert remember(routed).duplicate is False
    assert remember(review).duplicate is False

    assert lookup("ticket-1:10") is routed
    stored_review = lookup("ticket-2:11")
    assert stored_review is not None
    assert stored_review.decision.destination is None


def test_concurrent_repeats_keep_one_body() -> None:
    clear()
    notification = _notification("ticket-1:10", "ticket-1")
    results: list[bool] = []

    def once() -> None:
        results.append(remember(notification).duplicate)

    threads = [Thread(target=once) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(False) == 1
    assert lookup("ticket-1:10") is notification
