"""Tests for CSV-backed SQLite initialization."""

import sqlite3

from app.db.init_db import initialize_database


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    """Return row count for a database table."""

    cursor = connection.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cursor.fetchone()[0])


def test_initialize_database_creates_expected_tables(tmp_path) -> None:
    """Database initialization should be repeatable and load seed data."""

    db_path = tmp_path / "business_insight.db"

    first_counts = initialize_database(db_path=db_path)
    second_counts = initialize_database(db_path=db_path)

    assert db_path.exists()
    assert first_counts["products"] >= 5
    assert second_counts["orders"] >= 800

    with sqlite3.connect(db_path) as connection:
        assert _count_rows(connection, "products") >= 5
        assert _count_rows(connection, "orders") >= 800
