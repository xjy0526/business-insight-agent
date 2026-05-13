"""Safe read-only SQL helper for local business data analysis."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

try:
    import sqlparse as _sqlparse
except ImportError:  # pragma: no cover - exercised only in minimal environments.
    _sqlparse = None

from app.db.database import resolve_database_path

DANGEROUS_SQL_KEYWORDS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "insert",
    "pragma",
    "replace",
    "truncate",
    "update",
    "vacuum",
}


def _validate_readonly_sql(sql: str) -> str:
    """Validate that a SQL statement is a single read-only SELECT query."""

    statement = sql.strip()
    if not statement:
        raise ValueError("SQL query cannot be empty.")

    if _sqlparse is not None:
        parsed_statements = [item for item in _sqlparse.parse(statement) if str(item).strip()]
        if len(parsed_statements) != 1:
            raise ValueError("Only one SELECT statement is allowed.")

        parsed_statement = parsed_statements[0]
        statement_without_trailing_semicolon = str(parsed_statement).strip().rstrip(";").strip()
        if not statement_without_trailing_semicolon:
            raise ValueError("SQL query cannot be empty.")

        if parsed_statement.get_type().upper() != "SELECT":
            raise ValueError("Only SELECT queries are allowed.")
    else:
        statement_without_trailing_semicolon = statement.rstrip(";").strip()
        if ";" in statement_without_trailing_semicolon:
            raise ValueError("Only one SELECT statement is allowed.")

    normalized = statement_without_trailing_semicolon.lower()
    if not normalized.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    tokens = set(re.findall(r"\b[a-z_]+\b", normalized))
    blocked_tokens = tokens.intersection(DANGEROUS_SQL_KEYWORDS)
    if blocked_tokens:
        blocked = ", ".join(sorted(blocked_tokens))
        raise ValueError(f"Dangerous SQL keyword is not allowed: {blocked}")

    return statement_without_trailing_semicolon


def _get_readonly_connection() -> sqlite3.Connection:
    """Open SQLite in read-only mode so validation is not the only guardrail."""

    database_path = resolve_database_path()
    if database_path == ":memory:":
        raise ValueError("Read-only SQL tool does not support in-memory databases.")

    readonly_uri = f"file:{database_path}?mode=ro"
    connection = sqlite3.connect(readonly_uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def execute_readonly_query(sql: str) -> list[dict[str, Any]]:
    """Execute a safe SELECT query and return rows as dictionaries."""

    statement = _validate_readonly_sql(sql)

    with _get_readonly_connection() as connection:
        cursor = connection.execute(statement)
        return [dict(row) for row in cursor.fetchall()]
