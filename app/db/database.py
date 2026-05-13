"""SQLite connection helpers for BusinessInsight Agent."""

import sqlite3
from pathlib import Path

from app.config import get_settings

DEFAULT_DATABASE_PATH = Path("data/business_insight.db")
SQLITE_URL_PREFIX = "sqlite:///"


def resolve_database_path(db_path: str | Path | None = None) -> Path | str:
    """Resolve a SQLite database path from an explicit path or DATABASE_URL."""

    if db_path is not None:
        return Path(db_path)

    database_url = get_settings().database_url
    if database_url.startswith(SQLITE_URL_PREFIX):
        raw_path = database_url.removeprefix(SQLITE_URL_PREFIX)
        return raw_path if raw_path == ":memory:" else Path(raw_path)

    return DEFAULT_DATABASE_PATH


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create a SQLite connection and ensure the database directory exists."""

    database_path = resolve_database_path(db_path)

    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection
