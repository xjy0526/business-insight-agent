"""Tests for Agent trace persistence."""

import sqlite3

from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.db.init_db import initialize_database
from app.services.trace_service import TraceService, ensure_trace_table


def test_agent_execution_saves_trace() -> None:
    """Running the Agent should persist a trace row."""

    initialize_database()
    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    trace = TraceService().get_trace(result["trace_id"])

    assert trace is not None
    assert trace["trace_id"] == result["trace_id"]
    assert trace["user_query"] == "商品 P1001 最近 GMV 为什么下降？"
    assert trace["intent"] == "business_diagnosis"
    assert trace["tool_results"]
    assert trace["retrieved_docs"]
    assert trace["node_spans"]
    assert trace["node_spans"][0]["latency_ms"] >= 0
    assert "input_summary" in trace["node_spans"][0]
    assert "output_summary" in trace["node_spans"][0]
    assert trace["latency_ms"] >= 0


def test_trace_can_be_loaded_by_trace_id() -> None:
    """TraceService should return one persisted trace by ID."""

    result = run_agent("商品 P1001 最近 GMV 为什么下降？", cache_key="agent_analyze:test")

    trace = TraceService().get_trace(result["trace_id"])

    assert trace is not None
    assert trace["final_answer"]
    assert result["trace_id"] in trace["final_answer"]
    assert isinstance(trace["plan_steps"], list)
    assert isinstance(trace["node_spans"], list)
    assert trace["cache_key"] == "agent_analyze:test"
    assert trace["cache_hit"] is False


def test_list_traces_returns_recent_records() -> None:
    """TraceService should list recent trace records."""

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    traces = TraceService().list_traces(limit=5)

    assert traces
    assert any(trace["trace_id"] == result["trace_id"] for trace in traces)


def test_initialize_database_preserves_existing_trace_rows(tmp_path) -> None:
    """Seed-data reinitialization should not drop agent_traces."""

    db_path = tmp_path / "business_insight.db"
    initialize_database(db_path=db_path)
    state = AgentState(trace_id="trace-preserve-test", user_query="测试 trace 保留")
    state.intent = "business_diagnosis"
    state.final_answer = "测试回答"

    trace_service = TraceService(db_path=db_path)
    trace_service.save_trace(state, latency_ms=12)
    counts = initialize_database(db_path=db_path)

    assert counts["agent_traces"] == 1
    assert trace_service.get_trace("trace-preserve-test") is not None


def test_ensure_trace_table_handles_plain_sqlite_connections(tmp_path) -> None:
    """Trace schema migration should not require sqlite3.Row row_factory."""

    db_path = tmp_path / "plain_connection.db"
    with sqlite3.connect(db_path) as connection:
        ensure_trace_table(connection)
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(agent_traces)").fetchall()
        }

    assert {"trace_id", "node_spans", "cache_key", "cache_hit"}.issubset(columns)
