"""Trace persistence service for Agent execution observability."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent.state import AgentState
from app.db.database import get_connection

AGENT_TRACES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS agent_traces (
        trace_id TEXT PRIMARY KEY,
        user_query TEXT,
        intent TEXT,
        entity_id TEXT,
        plan_steps TEXT,
        tool_results TEXT,
        retrieved_docs TEXT,
        final_answer TEXT,
        reflection_result TEXT,
        node_spans TEXT,
        cache_key TEXT,
        cache_hit INTEGER DEFAULT 0,
        latency_ms INTEGER,
        error_type TEXT,
        created_at TEXT
    )
"""

JSON_COLUMNS = {
    "plan_steps",
    "tool_results",
    "retrieved_docs",
    "reflection_result",
    "node_spans",
}
TRACE_COLUMNS = {
    "node_spans": "TEXT",
    "cache_key": "TEXT",
    "cache_hit": "INTEGER DEFAULT 0",
}


def ensure_trace_table(connection: sqlite3.Connection) -> None:
    """Create the agent_traces table if it does not already exist."""

    connection.execute(AGENT_TRACES_SCHEMA)
    table_info_rows = connection.execute("PRAGMA table_info(agent_traces)").fetchall()
    existing_columns = {_extract_column_name(row) for row in table_info_rows}
    for column_name, column_type in TRACE_COLUMNS.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE agent_traces ADD COLUMN {column_name} {column_type}")


def _extract_column_name(row: sqlite3.Row | tuple[Any, ...]) -> str:
    """Read PRAGMA table_info column names with or without sqlite Row factory."""

    if isinstance(row, sqlite3.Row):
        return str(row["name"])
    return str(row[1])


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


def _to_json(value: Any) -> str:
    """Serialize trace payloads without escaping Chinese characters."""

    return json.dumps(value, ensure_ascii=False, default=str)


def _from_json(value: str | None) -> Any:
    """Deserialize a JSON column and keep invalid values inspectable."""

    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


class TraceService:
    """Persist and query Agent execution traces in SQLite."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def save_trace(
        self,
        state: AgentState,
        latency_ms: int,
        error_type: str | None = None,
    ) -> None:
        """Save one AgentState as an observability trace."""

        created_at = state.finished_at or _now_iso()
        inferred_error_type = error_type
        if inferred_error_type is None and state.errors:
            inferred_error_type = state.errors[0].get("node", "agent_error")

        with get_connection(self.db_path) as connection:
            ensure_trace_table(connection)
            connection.execute(
                """
                INSERT OR REPLACE INTO agent_traces (
                    trace_id,
                    user_query,
                    intent,
                    entity_id,
                    plan_steps,
                    tool_results,
                    retrieved_docs,
                    final_answer,
                    reflection_result,
                    node_spans,
                    cache_key,
                    cache_hit,
                    latency_ms,
                    error_type,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.trace_id,
                    state.user_query,
                    state.intent,
                    state.entity_id,
                    _to_json(state.plan_steps),
                    _to_json(state.tool_results),
                    _to_json(state.retrieved_docs),
                    state.final_answer,
                    _to_json(state.reflection_result),
                    _to_json(state.node_spans),
                    state.cache_key,
                    int(state.cache_hit),
                    latency_ms,
                    inferred_error_type,
                    created_at,
                ),
            )

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Fetch one trace by trace_id."""

        with get_connection(self.db_path) as connection:
            ensure_trace_table(connection)
            row = connection.execute(
                """
                SELECT
                    trace_id,
                    user_query,
                    intent,
                    entity_id,
                    plan_steps,
                    tool_results,
                    retrieved_docs,
                    final_answer,
                    reflection_result,
                    node_spans,
                    cache_key,
                    cache_hit,
                    latency_ms,
                    error_type,
                    created_at
                FROM agent_traces
                WHERE trace_id = ?
                """,
                (trace_id,),
            ).fetchone()

        return self._row_to_trace(row) if row is not None else None

    def list_traces(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent traces ordered by created_at descending."""

        safe_limit = max(1, min(limit, 100))
        with get_connection(self.db_path) as connection:
            ensure_trace_table(connection)
            rows = connection.execute(
                """
                SELECT
                    trace_id,
                    user_query,
                    intent,
                    entity_id,
                    plan_steps,
                    tool_results,
                    retrieved_docs,
                    final_answer,
                    reflection_result,
                    node_spans,
                    cache_key,
                    cache_hit,
                    latency_ms,
                    error_type,
                    created_at
                FROM agent_traces
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [self._row_to_trace(row) for row in rows]

    def _row_to_trace(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a SQLite row into a trace dictionary with parsed JSON fields."""

        trace = dict(row)
        for column in JSON_COLUMNS:
            trace[column] = _from_json(trace.get(column))
        trace["cache_hit"] = bool(trace.get("cache_hit"))
        return trace
