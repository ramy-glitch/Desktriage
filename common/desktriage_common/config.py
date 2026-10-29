"""Runtime settings read from the environment.

DATABASE_URL is how the API and the worker reach PostgreSQL.
WEBHOOK_URL is how the worker reaches the notification receiver. The API can
start without it.

Paths inside the worker container, overridable with CONFIG_DIR and MODELS_DIR:
  /app/config  routing rules, priority policy, confidence threshold
  /app/models  exported category classifier
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment values shared by the API and the worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    webhook_url: str | None = None
    config_dir: Path = Path("/app/config")
    models_dir: Path = Path("/app/models")

    @field_validator("database_url", "webhook_url")
    @classmethod
    def url_must_be_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


@lru_cache
def get_settings() -> Settings:
    """Read settings once per process."""
    return Settings()
