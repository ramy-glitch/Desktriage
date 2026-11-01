# The worker process loads settings, opens the database, loads the exported
# model once, and polls until it is asked to stop.
# A database or model failure stops startup before the loop starts.

import signal
from collections.abc import Callable

import pytest

from worker.app.main import main


def test_startup_loads_the_model_once_and_then_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    handlers: dict[int, object] = {}

    monkeypatch.setattr("worker.app.main.get_settings", lambda: order.append("settings"))
    monkeypatch.setattr("worker.app.main.check_session", lambda: order.append("database"))
    monkeypatch.setattr("worker.app.main.load_classifier", lambda: order.append("model"))
    monkeypatch.setattr(
        "worker.app.main.signal.signal",
        lambda signum, handler: handlers.__setitem__(signum, handler),
    )

    def poll(*, stop: Callable[[], bool]) -> None:
        order.append("loop")
        assert stop() is False
        handlers[signal.SIGINT](signal.SIGINT, None)
        assert stop() is True

    monkeypatch.setattr("worker.app.main.run", poll)

    main()

    assert order == ["settings", "database", "model", "loop"]
    assert signal.SIGINT in handlers
    assert signal.SIGTERM in handlers


def test_a_database_failure_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def fail() -> None:
        raise ConnectionError("postgresql://user:secret@db:5432/desktriage")

    monkeypatch.setattr("worker.app.main.get_settings", lambda: order.append("settings"))
    monkeypatch.setattr("worker.app.main.check_session", fail)
    monkeypatch.setattr("worker.app.main.load_classifier", lambda: order.append("model"))
    monkeypatch.setattr("worker.app.main.run", lambda **kwargs: order.append("loop"))
    monkeypatch.setattr("worker.app.main.signal.signal", lambda signum, handler: None)

    with pytest.raises(ConnectionError):
        main()

    assert order == ["settings"]


def test_a_model_failure_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def fail() -> None:
        raise RuntimeError("model file missing")

    monkeypatch.setattr("worker.app.main.get_settings", lambda: order.append("settings"))
    monkeypatch.setattr("worker.app.main.check_session", lambda: order.append("database"))
    monkeypatch.setattr("worker.app.main.load_classifier", fail)
    monkeypatch.setattr("worker.app.main.run", lambda **kwargs: order.append("loop"))
    monkeypatch.setattr("worker.app.main.signal.signal", lambda signum, handler: None)

    with pytest.raises(RuntimeError):
        main()

    assert order == ["settings", "database"]
