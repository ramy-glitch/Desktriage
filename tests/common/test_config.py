# Settings come from the environment. A blank URL is rejected.
# The webhook URL may be absent so the intake API can start without it.
# get_settings keeps the first read for the life of the process.

from pathlib import Path

import pytest
from pydantic import ValidationError

from desktriage_common.config import Settings, get_settings

_DATABASE_URL = "postgresql+psycopg://desktriage:desktriage@127.0.0.1:5432/desktriage"


def test_a_blank_database_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_a_blank_webhook_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", _DATABASE_URL)
    monkeypatch.setenv("WEBHOOK_URL", "  ")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_the_webhook_url_may_be_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", _DATABASE_URL)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == _DATABASE_URL
    assert settings.webhook_url is None
    assert settings.config_dir == Path("/app/config")
    assert settings.models_dir == Path("/app/models")


def test_get_settings_reads_once(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", _DATABASE_URL)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    try:
        first = get_settings()
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg://other:other@127.0.0.1:5432/other",
        )
        second = get_settings()
        assert first is second
        assert second.database_url == _DATABASE_URL
    finally:
        get_settings.cache_clear()
