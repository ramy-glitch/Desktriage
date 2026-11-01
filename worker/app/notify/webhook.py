"""POST the stored decision to WEBHOOK_URL.

Send the idempotency key from idempotency.py on every attempt, in the body
and in the Idempotency-Key header. Record the attempt on the one
webhook_deliveries row for that key: response status, time, and error.
A repeated key for a delivery that already succeeded does not POST again.
A timeout or a failed response raises NotifyError so the pipeline can ask
retry.py for another attempt.
"""

from collections.abc import Mapping

import httpx
from sqlalchemy import text

from desktriage_common.config import get_settings
from desktriage_common.db import get_session
from desktriage_common.logging import get_logger
from desktriage_common.schemas import WebhookNotification

from worker.app.notify.idempotency import decision_key
from worker.app.trace import StoredDecision

logger = get_logger("worker.notify")

WEBHOOK_TIMEOUT_SECONDS = 5.0

_LATEST_DECISION = text(
    """
    SELECT id
    FROM triage_decisions
    WHERE ticket_id = :ticket_id
    ORDER BY decided_at DESC, id DESC
    LIMIT 1
    """
)

_DELIVERY = text(
    """
    SELECT attempt_number, response_status
    FROM webhook_deliveries
    WHERE idempotency_key = :idempotency_key
    """
)

_UPSERT_DELIVERY = text(
    """
    INSERT INTO webhook_deliveries (
        ticket_id,
        idempotency_key,
        attempt_number,
        response_status,
        error_text
    )
    VALUES (
        :ticket_id,
        :idempotency_key,
        :attempt_number,
        :response_status,
        :error_text
    )
    ON CONFLICT (idempotency_key) DO UPDATE
    SET attempt_number = EXCLUDED.attempt_number,
        response_status = EXCLUDED.response_status,
        error_text = EXCLUDED.error_text,
        delivered_at = now()
    WHERE webhook_deliveries.response_status IS NULL
       OR webhook_deliveries.response_status < 200
       OR webhook_deliveries.response_status >= 300
    """
)


class NotifyError(RuntimeError):
    """The webhook delivery did not succeed."""


def notify(stored: StoredDecision) -> None:
    """Deliver one stored decision, or raise NotifyError when the receiver does not accept it."""
    url = _webhook_url()
    key, existing = _notification_state(stored.ticket_id)
    if _succeeded(existing):
        logger.info("event=webhook_duplicate ticket_id=%s", stored.ticket_id)
        return

    attempt = 1 if existing is None else int(existing["attempt_number"]) + 1
    notification = WebhookNotification(
        idempotency_key=key,
        ticket_id=stored.ticket_id,
        status=stored.status,
        decision=stored.decision,
    )
    try:
        status_code = _post(url, notification)
    except NotifyError as exc:
        _save(stored.ticket_id, key, attempt, response_status=None, error_text=str(exc))
        _log_failure(stored.ticket_id, attempt, exc)
        raise

    if _accepted(status_code):
        _save(stored.ticket_id, key, attempt, response_status=status_code, error_text=None)
        logger.info(
            "event=webhook_delivered ticket_id=%s attempt=%s status_code=%s",
            stored.ticket_id,
            attempt,
            status_code,
        )
        return

    failure = NotifyError(f"webhook returned {status_code}")
    _save(
        stored.ticket_id,
        key,
        attempt,
        response_status=status_code,
        error_text=str(failure),
    )
    _log_failure(stored.ticket_id, attempt, failure)
    raise failure


def _webhook_url() -> str:
    url = get_settings().webhook_url
    if not isinstance(url, str) or not url.strip():
        raise NotifyError("WEBHOOK_URL is not set")
    return url.strip()


def _notification_state(ticket_id: str) -> tuple[str, Mapping[str, object] | None]:
    with get_session() as session:
        decision = session.execute(
            _LATEST_DECISION,
            {"ticket_id": ticket_id},
        ).mappings().one_or_none()
        if decision is None:
            raise NotifyError("the ticket has no stored decision")
        key = decision_key(ticket_id, int(decision["id"]))
        existing = session.execute(
            _DELIVERY,
            {"idempotency_key": key},
        ).mappings().one_or_none()
    return key, existing


def _post(url: str, notification: WebhookNotification) -> int:
    try:
        response = httpx.post(
            url,
            json=notification.model_dump(mode="json"),
            headers={"Idempotency-Key": notification.idempotency_key},
            timeout=WEBHOOK_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise NotifyError("timeout") from exc
    except httpx.RequestError as exc:
        raise NotifyError("connection failed") from exc
    return int(response.status_code)


def _save(
    ticket_id: str,
    key: str,
    attempt: int,
    *,
    response_status: int | None,
    error_text: str | None,
) -> None:
    with get_session() as session:
        session.execute(
            _UPSERT_DELIVERY,
            {
                "ticket_id": ticket_id,
                "idempotency_key": key,
                "attempt_number": attempt,
                "response_status": response_status,
                "error_text": error_text,
            },
        )


def _succeeded(existing: Mapping[str, object] | None) -> bool:
    if existing is None:
        return False
    return _accepted(existing["response_status"])


def _accepted(status_code: object) -> bool:
    return isinstance(status_code, int) and not isinstance(status_code, bool) and 200 <= status_code <= 299


def _log_failure(ticket_id: str, attempt: int, exc: Exception) -> None:
    logger.error(
        "event=webhook_failed ticket_id=%s attempt=%s error_type=%s",
        ticket_id,
        attempt,
        type(exc).__name__,
    )
