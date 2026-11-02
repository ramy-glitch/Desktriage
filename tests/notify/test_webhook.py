# The worker posts the decision to the webhook with an idempotency key.
# A second attempt with the same key does not create a second logical notification.
# A failed delivery is recorded and can be retried.

from collections.abc import Mapping

import httpx
import pytest

from desktriage_common.enums import Category, Priority
from desktriage_common.schemas import TriageDecision
from desktriage_common.statuses import Status
from worker.app.notify.idempotency import IdempotencyError, decision_key
from worker.app.notify.webhook import NotifyError, notify
from worker.app.trace import StoredDecision


class _Settings:
    webhook_url = "http://webhook:8001/notifications"


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _Store:
    def __init__(self, decision_id: int | None = 10) -> None:
        self.decision_id = decision_id
        self.deliveries: dict[str, Mapping[str, object]] = {}
        self.writes: list[Mapping[str, object]] = []


class _Session:
    def __init__(self, store: _Store) -> None:
        self._store = store

    def execute(self, statement: object, params: Mapping[str, object]) -> "_Result":
        sql = str(statement)
        if "FROM triage_decisions" in sql:
            if self._store.decision_id is None:
                return _Result(None)
            return _Result({"id": self._store.decision_id})
        if "FROM webhook_deliveries" in sql:
            key = str(params["idempotency_key"])
            return _Result(self._store.deliveries.get(key))
        if "INSERT INTO webhook_deliveries" in sql:
            self._store.writes.append(dict(params))
            key = str(params["idempotency_key"])
            self._store.deliveries[key] = {
                "attempt_number": params["attempt_number"],
                "response_status": params["response_status"],
            }
            return _Result(None)
        raise AssertionError(sql)


class _Result:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> "_Result":
        return self

    def one_or_none(self) -> Mapping[str, object] | None:
        return self._row


class _Sessions:
    def __init__(self, store: _Store) -> None:
        self._store = store

    def __enter__(self) -> _Session:
        return _Session(self._store)

    def __exit__(self, *args: object) -> bool:
        return False


def _stored() -> StoredDecision:
    return StoredDecision(
        ticket_id="ticket-1",
        status=Status.ROUTED,
        decision=TriageDecision(
            category=Category.CLAIMS_AND_APPEALS,
            priority=Priority.P2,
            confidence=0.9,
            requires_human_review=False,
            destination="claims_support",
            model_version="abc123",
        ),
    )


def _install(monkeypatch: pytest.MonkeyPatch, store: _Store, post: object) -> None:
    monkeypatch.setattr("worker.app.notify.webhook.get_settings", lambda: _Settings())
    monkeypatch.setattr("worker.app.notify.webhook.get_session", lambda: _Sessions(store))
    monkeypatch.setattr("worker.app.notify.webhook.httpx.post", post)


def test_the_key_uses_the_ticket_and_decision() -> None:
    assert decision_key("ticket-1", 10) == "ticket-1:10"
    assert decision_key(" ticket-1 ", 10) == "ticket-1:10"
    assert decision_key("ticket-1", 11) == "ticket-1:11"


def test_a_blank_ticket_or_decision_is_rejected() -> None:
    with pytest.raises(IdempotencyError):
        decision_key(" ", 10)
    with pytest.raises(IdempotencyError):
        decision_key("ticket-1", 0)


def test_notify_posts_the_decision_and_records_one_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    posts: list[tuple[str, Mapping[str, object], Mapping[str, str], float]] = []

    def post(url: str, *, json: Mapping[str, object], headers: Mapping[str, str], timeout: float) -> _Response:
        posts.append((url, json, headers, timeout))
        return _Response(204)

    _install(monkeypatch, store, post)
    notify(_stored())

    url, body, headers, timeout = posts[0]
    assert url == "http://webhook:8001/notifications"
    assert timeout == 5.0
    assert headers["Idempotency-Key"] == "ticket-1:10"
    assert body["idempotency_key"] == "ticket-1:10"
    assert body["ticket_id"] == "ticket-1"
    assert body["status"] == "routed"
    assert body["decision"]["destination"] == "claims_support"
    assert store.writes == [
        {
            "ticket_id": "ticket-1",
            "idempotency_key": "ticket-1:10",
            "attempt_number": 1,
            "response_status": 204,
            "error_text": None,
        }
    ]


def test_a_second_post_of_the_same_decision_is_not_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    posts: list[int] = []

    def post(url: str, *, json: Mapping[str, object], headers: Mapping[str, str], timeout: float) -> _Response:
        posts.append(1)
        return _Response(200)

    _install(monkeypatch, store, post)
    notify(_stored())
    notify(_stored())

    assert posts == [1]
    assert len(store.writes) == 1


def test_a_later_decision_gets_a_new_key(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()

    def post(url: str, *, json: Mapping[str, object], headers: Mapping[str, str], timeout: float) -> _Response:
        return _Response(200)

    _install(monkeypatch, store, post)
    notify(_stored())
    store.decision_id = 11
    notify(_stored())

    assert [write["idempotency_key"] for write in store.writes] == [
        "ticket-1:10",
        "ticket-1:11",
    ]


def test_a_failed_response_is_recorded_and_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    statuses = iter([503, 200])

    def post(url: str, *, json: Mapping[str, object], headers: Mapping[str, str], timeout: float) -> _Response:
        return _Response(next(statuses))

    _install(monkeypatch, store, post)

    with pytest.raises(NotifyError, match="webhook returned 503"):
        notify(_stored())
    notify(_stored())

    assert store.writes[0]["attempt_number"] == 1
    assert store.writes[0]["response_status"] == 503
    assert store.writes[0]["error_text"] == "webhook returned 503"
    assert store.writes[1]["attempt_number"] == 2
    assert store.writes[1]["response_status"] == 200
    assert store.writes[0]["idempotency_key"] == store.writes[1]["idempotency_key"]


def test_a_timeout_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()

    def post(url: str, *, json: Mapping[str, object], headers: Mapping[str, str], timeout: float) -> _Response:
        raise httpx.TimeoutException("timed out talking to the receiver")

    _install(monkeypatch, store, post)

    with pytest.raises(NotifyError, match="timeout"):
        notify(_stored())

    assert store.writes == [
        {
            "ticket_id": "ticket-1",
            "idempotency_key": "ticket-1:10",
            "attempt_number": 1,
            "response_status": None,
            "error_text": "timeout",
        }
    ]


def test_a_missing_webhook_url_does_not_post(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[int] = []
    monkeypatch.setattr(
        "worker.app.notify.webhook.get_settings",
        lambda: type("_Missing", (), {"webhook_url": None})(),
    )
    monkeypatch.setattr(
        "worker.app.notify.webhook.httpx.post",
        lambda *args, **kwargs: posts.append(1),
    )

    with pytest.raises(NotifyError, match="WEBHOOK_URL is not set"):
        notify(_stored())

    assert posts == []


def test_a_boolean_decision_id_is_rejected() -> None:
    with pytest.raises(IdempotencyError):
        decision_key("ticket-1", True)
    with pytest.raises(IdempotencyError):
        decision_key("ticket-1", -3)


def test_a_connection_error_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()

    def post(
        url: str,
        *,
        json: Mapping[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> _Response:
        raise httpx.ConnectError("connection refused")

    _install(monkeypatch, store, post)

    with pytest.raises(NotifyError, match="connection failed"):
        notify(_stored())

    assert store.writes == [
        {
            "ticket_id": "ticket-1",
            "idempotency_key": "ticket-1:10",
            "attempt_number": 1,
            "response_status": None,
            "error_text": "connection failed",
        }
    ]


def test_a_missing_decision_does_not_post(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store(decision_id=None)
    posts: list[int] = []

    def post(
        url: str,
        *,
        json: Mapping[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> _Response:
        posts.append(1)
        return _Response(200)

    _install(monkeypatch, store, post)

    with pytest.raises(NotifyError, match="no stored decision"):
        notify(_stored())

    assert posts == []
    assert store.writes == []


def test_a_redirect_is_a_failed_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()

    def post(
        url: str,
        *,
        json: Mapping[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> _Response:
        return _Response(302)

    _install(monkeypatch, store, post)

    with pytest.raises(NotifyError, match="webhook returned 302"):
        notify(_stored())

    assert store.writes[0]["response_status"] == 302
    assert store.writes[0]["error_text"] == "webhook returned 302"
