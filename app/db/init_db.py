"""Initialize the local SQLite database from CSV seed data."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from app.db.database import get_connection, resolve_database_path
from app.services.trace_service import ensure_trace_table

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

TABLE_SCHEMAS = {
    "products": """
        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            brand TEXT NOT NULL,
            price REAL NOT NULL
        )
    """,
    "orders": """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            payment_amount REAL NOT NULL,
            refund_flag INTEGER NOT NULL,
            channel TEXT NOT NULL
        )
    """,
    "traffic": """
        CREATE TABLE traffic (
            date TEXT NOT NULL,
            product_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            exposure INTEGER NOT NULL,
            clicks INTEGER NOT NULL,
            add_to_cart INTEGER NOT NULL,
            orders INTEGER NOT NULL
        )
    """,
    "reviews": """
        CREATE TABLE reviews (
            review_id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            content TEXT NOT NULL,
            review_date TEXT NOT NULL
        )
    """,
    "campaigns": """
        CREATE TABLE campaigns (
            campaign_id TEXT PRIMARY KEY,
            campaign_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            eligible_category TEXT NOT NULL,
            discount_rule TEXT NOT NULL
        )
    """,
}

CSV_TABLES = {
    "products": "products.csv",
    "orders": "orders.csv",
    "traffic": "traffic.csv",
    "reviews": "reviews.csv",
    "campaigns": "campaigns.csv",
}


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read one CSV file as dictionaries while keeping column order."""

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV seed file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _reset_tables(connection: sqlite3.Connection) -> None:
    """Drop and recreate seed-data tables so initialization is repeatable."""

    for table_name in CSV_TABLES:
        connection.execute(f"DROP TABLE IF EXISTS {table_name}")

    for schema in TABLE_SCHEMAS.values():
        connection.execute(schema)


def _insert_rows(
    connection: sqlite3.Connection,
    table_name: str,
    rows: list[dict[str, str]],
) -> int:
    """Insert CSV rows into a table using the CSV header as columns."""

    if not rows:
        return 0

    columns = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(columns)
    values = [tuple(row[column] for column in columns) for row in rows]

    connection.executemany(
        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders})",
        values,
    )
    return len(rows)


def initialize_database(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Create SQLite tables and load all seed CSV files."""

    data_path = Path(data_dir)
    load_counts: dict[str, int] = {}

    with get_connection(db_path) as connection:
        _reset_tables(connection)
        ensure_trace_table(connection)

        for table_name, csv_file in CSV_TABLES.items():
            rows = _read_csv_rows(data_path / csv_file)
            load_counts[table_name] = _insert_rows(connection, table_name, rows)

        trace_count = connection.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0]
        load_counts["agent_traces"] = int(trace_count)

    return load_counts


def main() -> None:
    """CLI entrypoint used by `python -m app.db.init_db`."""

    database_path = resolve_database_path()
    load_counts = initialize_database()
    print(f"Initialized SQLite database: {database_path}")
    for table_name, row_count in load_counts.items():
        print(f"- {table_name}: {row_count} rows")


if __name__ == "__main__":
    main()
