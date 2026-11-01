"""Remember notifications received by this local mock.

Store the body and the idempotency key. A second POST with the same key is a
duplicate delivery, not a second ticket. An in-memory store is enough for local
verification. The receipt log leaves ticket query text out. The notification
body does not carry that text.
"""

from dataclasses import dataclass
from threading import Lock

from desktriage_common.logging import get_logger
from desktriage_common.schemas import WebhookNotification

logger = get_logger("webhook.receipts")

_lock = Lock()
_received: dict[str, WebhookNotification] = {}


@dataclass(frozen=True)
class Receipt:
    """One accepted delivery, marked when the key was already stored."""

    idempotency_key: str
    ticket_id: str
    duplicate: bool


def remember(notification: WebhookNotification) -> Receipt:
    """Store a new notification, or keep the original when the key repeats."""
    with _lock:
        existing = _received.get(notification.idempotency_key)
        if existing is None:
            _received[notification.idempotency_key] = notification
            duplicate = False
        else:
            duplicate = True
    logger.info(
        "event=notification_received ticket_id=%s status=%s duplicate=%s",
        notification.ticket_id,
        notification.status.value,
        duplicate,
    )
    return Receipt(
        idempotency_key=notification.idempotency_key,
        ticket_id=notification.ticket_id,
        duplicate=duplicate,
    )


def lookup(idempotency_key: str) -> WebhookNotification | None:
    """Return the first body stored for this key."""
    with _lock:
        return _received.get(idempotency_key)


def clear() -> None:
    """Drop the in-memory receipts. Tests use this between cases."""
    with _lock:
        _received.clear()
