"""Tests for Trace Stats observability aggregation."""

from app.agent.graph import run_agent
from app.config import get_settings
from app.db.init_db import initialize_database
from app.main import app
from app.services.trace_service import TraceService
from fastapi.testclient import TestClient


def test_get_trace_stats_empty_safe(tmp_path) -> None:
    """Trace stats should be safe on an empty trace table."""

    stats = TraceService(db_path=tmp_path / "empty_traces.db").get_trace_stats()

    assert stats["total_traces"] >= 0
    assert stats["avg_latency_ms"] == 0.0
    assert stats["p95_latency_ms"] == 0
    assert stats["intent_distribution"] == {}
    assert stats["slowest_nodes"] == []


def test_get_trace_stats_after_agent_runs() -> None:
    """Trace stats should aggregate multiple Agent runs."""

    initialize_database()
    run_agent("商品 P1001 最近 GMV 为什么下降？")
    run_agent("P1001 4 月退款率为什么异常升高？")

    stats = TraceService().get_trace_stats(limit=20)

    assert stats["total_traces"] >= 2
    assert "avg_latency_ms" in stats
    assert "p50_latency_ms" in stats
    assert "p95_latency_ms" in stats
    assert stats["intent_distribution"]["business_diagnosis"] >= 1
    assert stats["recent_traces"]
    assert "token_usage_summary" in stats
    assert "provider_status_distribution" in stats


def test_get_node_stats() -> None:
    """Node stats should aggregate latency and error counts from node_spans."""

    initialize_database()
    run_agent("商品 P1001 最近 GMV 为什么下降？")

    node_stats = TraceService().get_node_stats(limit=20)
    node_names = {item["node"] for item in node_stats}

    assert "intent_router_node" in node_names or "planner_node" in node_names
    assert all("avg_latency_ms" in item for item in node_stats)
    assert all("p95_latency_ms" in item for item in node_stats)
    assert all("error_count" in item for item in node_stats)


def test_trace_stats_api() -> None:
    """Trace stats API should return aggregate observability fields."""

    initialize_database()
    client = TestClient(app)
    client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？", "use_cache": False},
    )

    response = client.get("/api/traces/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total_traces" in data
    assert "slowest_nodes" in data
    assert "intent_distribution" in data
    assert "alerts" in data


def test_trace_stats_latency_alert(monkeypatch) -> None:
    """Trace stats should emit threshold-based observability alerts."""

    initialize_database()
    run_agent("商品 P1001 最近 GMV 为什么下降？")
    monkeypatch.setenv("TRACE_ALERT_P95_LATENCY_MS", "0")
    get_settings.cache_clear()

    stats = TraceService().get_trace_stats(limit=5)

    assert any(alert["type"] == "latency" for alert in stats["alerts"])


def test_trace_nodes_and_errors_api() -> None:
    """Trace nodes and errors endpoints should be available for dashboards."""

    initialize_database()
    client = TestClient(app)
    client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？", "use_cache": False},
    )

    nodes_response = client.get("/api/traces/nodes")
    errors_response = client.get("/api/traces/errors")
    recent_response = client.get("/api/traces/recent", params={"limit": 5})

    assert nodes_response.status_code == 200
    assert errors_response.status_code == 200
    assert recent_response.status_code == 200
    assert isinstance(nodes_response.json(), list)
    assert "top_error_nodes" in errors_response.json()
    assert isinstance(recent_response.json(), list)
