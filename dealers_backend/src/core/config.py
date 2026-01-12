from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Application configuration loaded from environment variables."""

    database_url: str
    app_title: str = "Dealers Manager API"
    app_version: str = "0.1.0"


def _must_getenv(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Set it in the container .env (or deployment env)."
        )
    return value


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Load and return application settings.

    Expected environment variables:
      - DATABASE_URL: PostgreSQL DSN, e.g. postgresql://user:pass@host:port/db

    Returns:
        Settings: A settings object used throughout the app.
    """
    return Settings(
        database_url=_must_getenv("DATABASE_URL"),
    )
