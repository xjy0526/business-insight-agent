"""Trace persistence service for Agent execution observability."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Any

from app.agent.state import AgentState
from app.config import get_settings
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


def _safe_json_list(value: Any) -> list[dict[str, Any]]:
    """Return a list of dicts from parsed JSON-like values without raising."""

    parsed_value = _from_json(value) if isinstance(value, str) else value
    if not isinstance(parsed_value, list):
        return []
    return [item for item in parsed_value if isinstance(item, dict)]


def _percentile(values: list[int], percentile: float) -> int:
    """Calculate a nearest-rank percentile for latency values."""

    if not values:
        return 0
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, ceil(percentile * len(sorted_values)) - 1))
    return sorted_values[index]


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

        safe_limit = max(1, min(limit, 500))
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

    def get_trace_stats(self, limit: int = 100) -> dict[str, Any]:
        """Aggregate recent trace records for lightweight observability."""

        safe_limit = max(1, min(limit, 500))
        traces = self.list_traces(limit=safe_limit)
        latencies = self._trace_latencies(traces)
        trace_count = len(traces)
        total_trace_count = self._count_traces()
        avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        p50_latency_ms = _percentile(latencies, 0.50)
        p95_latency_ms = _percentile(latencies, 0.95)
        intent_distribution = self._intent_distribution_from_traces(traces)
        error_summary = self._error_summary_from_traces(traces)
        node_stats = self._node_stats_from_traces(traces)
        error_rate = (
            round(sum(1 for trace in traces if trace.get("error_type")) / trace_count, 6)
            if trace_count
            else 0.0
        )
        cache_hit_rate = (
            round(sum(1 for trace in traces if trace.get("cache_hit")) / trace_count, 6)
            if trace_count
            else 0.0
        )
        token_usage_summary = self._token_usage_summary_from_traces(traces)
        provider_status_distribution = self._provider_status_distribution_from_traces(traces)
        slowest_nodes = sorted(
            node_stats,
            key=lambda item: (item["avg_latency_ms"], item["p95_latency_ms"]),
            reverse=True,
        )[:10]
        recent_traces = [
            {
                "trace_id": trace.get("trace_id"),
                "user_query": trace.get("user_query"),
                "intent": trace.get("intent"),
                "entity_id": trace.get("entity_id"),
                "latency_ms": trace.get("latency_ms"),
                "cache_hit": trace.get("cache_hit"),
                "error_type": trace.get("error_type"),
                "created_at": trace.get("created_at"),
                "llm_provider": self._llm_metadata_from_trace(trace).get("provider"),
                "provider_status": self._llm_metadata_from_trace(trace).get("provider_status"),
            }
            for trace in traces[:20]
        ]
        node_latency_ms = {
            item["node"]: {
                "count": item["count"],
                "avg_latency_ms": item["avg_latency_ms"],
                "p95_latency_ms": item["p95_latency_ms"],
                "error_count": item["error_count"],
            }
            for item in node_stats
        }
        return {
            "total_traces": total_trace_count,
            "trace_count": trace_count,
            "avg_latency_ms": avg_latency_ms,
            "p50_latency_ms": p50_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "error_rate": error_rate,
            "cache_hit_rate": cache_hit_rate,
            "intent_distribution": intent_distribution,
            "intent_counts": intent_distribution,
            "top_error_nodes": error_summary["top_error_nodes"],
            "error_type_distribution": error_summary["error_type_distribution"],
            "error_type_counts": error_summary["error_type_distribution"],
            "slowest_nodes": slowest_nodes,
            "node_latency_ms": node_latency_ms,
            "token_usage_summary": token_usage_summary,
            "provider_status_distribution": provider_status_distribution,
            "alerts": self._build_alerts(
                p95_latency_ms=p95_latency_ms,
                error_rate=error_rate,
            ),
            "recent_traces": recent_traces,
        }

    def get_node_stats(self, limit: int = 500) -> list[dict[str, Any]]:
        """Aggregate per-node latency and error counts from trace node_spans."""

        return self._node_stats_from_traces(self.list_traces(limit=limit))

    def get_intent_distribution(self, limit: int = 500) -> dict[str, int]:
        """Return recent trace counts grouped by recognized intent."""

        return self._intent_distribution_from_traces(self.list_traces(limit=limit))

    def get_error_summary(self, limit: int = 500) -> dict[str, Any]:
        """Return recent top-level and per-node error summaries."""

        traces = self.list_traces(limit=limit)
        summary = self._error_summary_from_traces(traces)
        trace_count = len(traces)
        summary["error_rate"] = (
            round(sum(1 for trace in traces if trace.get("error_type")) / trace_count, 6)
            if trace_count
            else 0.0
        )
        summary["total_traces"] = trace_count
        return summary

    def _row_to_trace(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a SQLite row into a trace dictionary with parsed JSON fields."""

        trace = dict(row)
        for column in JSON_COLUMNS:
            trace[column] = _from_json(trace.get(column))
        trace["cache_hit"] = bool(trace.get("cache_hit"))
        return trace

    def _trace_latencies(self, traces: list[dict[str, Any]]) -> list[int]:
        """Collect valid trace-level latencies."""

        latencies: list[int] = []
        for trace in traces:
            latency = trace.get("latency_ms")
            if latency is None:
                continue
            try:
                latencies.append(int(latency))
            except (TypeError, ValueError):
                continue
        return latencies

    def _count_traces(self) -> int:
        """Count all persisted traces in the backing table."""

        with get_connection(self.db_path) as connection:
            ensure_trace_table(connection)
            row = connection.execute("SELECT COUNT(*) AS count FROM agent_traces").fetchone()
        return int(row["count"]) if row is not None else 0

    def _intent_distribution_from_traces(
        self,
        traces: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Aggregate intent counts from traces."""

        intent_distribution: dict[str, int] = {}
        for trace in traces:
            intent = str(trace.get("intent") or "unknown")
            intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
        return intent_distribution

    def _node_stats_from_traces(self, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggregate latency and error stats from parsed node_spans."""

        node_latency_values: dict[str, list[int]] = {}
        node_error_counts: dict[str, int] = {}
        for trace in traces:
            for span in _safe_json_list(trace.get("node_spans")):
                node = str(span.get("node") or "unknown")
                try:
                    latency_ms = int(span.get("latency_ms", 0))
                except (TypeError, ValueError):
                    latency_ms = 0
                node_latency_values.setdefault(node, []).append(latency_ms)
                if span.get("error_type"):
                    node_error_counts[node] = node_error_counts.get(node, 0) + 1

        stats = [
            {
                "node": node,
                "count": len(values),
                "avg_latency_ms": round(sum(values) / len(values), 2) if values else 0.0,
                "p95_latency_ms": _percentile(values, 0.95),
                "error_count": node_error_counts.get(node, 0),
            }
            for node, values in node_latency_values.items()
        ]
        return sorted(stats, key=lambda item: item["node"])

    def _error_summary_from_traces(self, traces: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate top-level error types and node-level errors from traces."""

        error_type_distribution: dict[str, int] = {}
        error_node_counts: dict[str, int] = {}
        for trace in traces:
            error_type = trace.get("error_type")
            if error_type:
                error_type_key = str(error_type)
                error_type_distribution[error_type_key] = (
                    error_type_distribution.get(error_type_key, 0) + 1
                )

            for span in _safe_json_list(trace.get("node_spans")):
                if span.get("error_type"):
                    node = str(span.get("node") or "unknown")
                    error_node_counts[node] = error_node_counts.get(node, 0) + 1

        top_error_nodes = [
            {"node": node, "count": count}
            for node, count in sorted(
                error_node_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]
        return {
            "error_type_distribution": error_type_distribution,
            "top_error_nodes": top_error_nodes,
        }

    def _llm_metadata_from_trace(self, trace: dict[str, Any]) -> dict[str, Any]:
        """Return trace-safe LLM metadata from tool_results when present."""

        tool_results = trace.get("tool_results", {})
        if not isinstance(tool_results, dict):
            return {}
        metadata = tool_results.get("llm_provider", {})
        return metadata if isinstance(metadata, dict) else {}

    def _token_usage_summary_from_traces(self, traces: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate token usage and estimated cost from provider metadata."""

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        retry_count = 0
        for trace in traces:
            metadata = self._llm_metadata_from_trace(trace)
            usage = metadata.get("token_usage", {})
            if not isinstance(usage, dict):
                continue
            prompt_tokens += self._safe_int(usage.get("prompt_tokens"))
            completion_tokens += self._safe_int(usage.get("completion_tokens"))
            total_tokens += self._safe_int(usage.get("total_tokens"))
            retry_count += self._safe_int(metadata.get("retry_count"))

        settings = get_settings()
        estimated_cost = (
            prompt_tokens / 1000 * settings.trace_token_cost_per_1k_input
            + completion_tokens / 1000 * settings.trace_token_cost_per_1k_output
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "retry_count": retry_count,
            "estimated_cost": round(estimated_cost, 6),
            "currency": "USD",
            "cost_model": "configured_per_1k_tokens",
        }

    def _provider_status_distribution_from_traces(
        self,
        traces: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Aggregate LLM provider status labels from recent traces."""

        distribution: dict[str, int] = {}
        for trace in traces:
            metadata = self._llm_metadata_from_trace(trace)
            status = str(metadata.get("provider_status") or "unknown")
            distribution[status] = distribution.get(status, 0) + 1
        return distribution

    def _build_alerts(self, p95_latency_ms: int, error_rate: float) -> list[dict[str, Any]]:
        """Build simple threshold alerts for the dashboard."""

        settings = get_settings()
        alerts: list[dict[str, Any]] = []
        if p95_latency_ms >= settings.trace_alert_p95_latency_ms:
            alerts.append(
                {
                    "type": "latency",
                    "level": "warning",
                    "message": "P95 latency exceeded configured threshold.",
                    "actual": p95_latency_ms,
                    "threshold": settings.trace_alert_p95_latency_ms,
                }
            )
        if error_rate >= settings.trace_alert_error_rate and error_rate > 0:
            alerts.append(
                {
                    "type": "error_rate",
                    "level": "warning",
                    "message": "Trace error rate exceeded configured threshold.",
                    "actual": error_rate,
                    "threshold": settings.trace_alert_error_rate,
                }
            )
        return alerts

    def _safe_int(self, value: Any) -> int:
        """Convert numeric-ish trace values to int safely."""

        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
