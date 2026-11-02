# The health route reports that this process is up and whether PostgreSQL answered.
# A database failure during startup stops the process. The connection string
# stays out of the log and out of the HTTP body.

import traceback

import pytest
from fastapi.testclient import TestClient


def test_health_reports_a_ready_database(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.app.routes.health.check_session", lambda: None)

    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_hides_a_database_error(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> None:
        raise RuntimeError("postgresql://desktriage:secret@db:5432/desktriage")

    monkeypatch.setattr("api.app.routes.health.check_session", fail)

    response = api_client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "ok", "database": "unavailable"}
    assert "secret" not in response.text


def test_startup_stops_when_the_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: list[str] = []

    monkeypatch.setattr("api.app.main.get_settings", lambda: object())
    monkeypatch.setattr(
        "api.app.main._logger.error",
        lambda message, *args: logged.append(message % args if args else message),
    )

    def fail() -> None:
        raise ConnectionError("postgresql://desktriage:secret@db:5432/desktriage")

    monkeypatch.setattr("api.app.main.check_session", fail)
    from api.app.main import create_app

    with pytest.raises(BaseException) as caught:
        with TestClient(create_app()):
            pass

    assert "ConnectionError" in "".join(traceback.format_exception(caught.value))
    assert logged == ["event=startup_failure error_type=ConnectionError"]
    assert "secret" not in logged[0]
