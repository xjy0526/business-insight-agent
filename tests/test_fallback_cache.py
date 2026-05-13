"""Tests for cache and fallback stability behavior."""

from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.db.init_db import initialize_database
from app.main import app
from app.services.cache_service import CacheService
from app.services.fallback_service import FallbackService
from app.services.trace_service import TraceService
from fastapi.testclient import TestClient


def test_same_query_hits_cache_on_second_request() -> None:
    """The analyze API should cache identical queries for five minutes."""

    initialize_database()
    CacheService().clear_cache()
    client = TestClient(app)

    first = client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？"},
    )
    second = client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["cache_key"] == first.json()["cache_key"]
    assert second.json()["trace_id"] != first.json()["trace_id"]
    assert f"trace_id: {second.json()['trace_id']}" in second.json()["answer"]

    cache_hit_trace = TraceService().get_trace(second.json()["trace_id"])
    assert cache_hit_trace is not None
    assert cache_hit_trace["cache_hit"] is True
    assert cache_hit_trace["cache_key"] == second.json()["cache_key"]
    assert cache_hit_trace["node_spans"][0]["node"] == "cache_hit"


def test_cache_service_records_cache_hit_trace() -> None:
    """CacheService should own request-scoped trace creation for cache hits."""

    initialize_database()
    cache = CacheService()
    cache_key = cache.build_key("cache service trace test")
    cached_payload = {
        "trace_id": "original-trace",
        "intent": "business_diagnosis",
        "answer": "## 诊断\n已有缓存报告\n\n---\ntrace_id: original-trace",
        "tool_results": {"compare_periods": {"product_id": "P1001"}},
        "retrieved_docs": [{"source": "campaign_rules.md", "score": 0.9}],
        "latency_ms": 99,
        "cached": False,
        "cache_key": cache_key,
    }

    payload = cache.build_cache_hit_response(
        query="cache service trace test",
        key=cache_key,
        cached_payload=cached_payload,
        latency_ms=1,
    )

    trace = TraceService().get_trace(payload["trace_id"])
    assert payload["cached"] is True
    assert payload["trace_id"] != "original-trace"
    assert f"trace_id: {payload['trace_id']}" in payload["answer"]
    assert trace is not None
    assert trace["cache_hit"] is True
    assert trace["node_spans"][0]["node"] == "cache_hit"


def test_empty_rag_result_does_not_crash_agent(monkeypatch) -> None:
    """Empty RAG results should return a clear fallback evidence message."""

    initialize_database()

    def empty_search(query: str) -> dict:
        return {"query": query, "results": [], "evidence_summary": ""}

    monkeypatch.setattr("app.agent.nodes.search_business_knowledge", empty_search)
    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert result["final_answer"]
    assert result["retrieved_docs"] == []
    assert "未检索到足够知识证据" in result["final_answer"]


def test_fallback_generates_report_for_metrics_failure() -> None:
    """Fallback service should explain metrics failures in the report."""

    state = AgentState(trace_id="test-trace", user_query="商品 P1001 最近 GMV 为什么下降？")
    state.intent = "business_diagnosis"
    state.entity_id = "P1001"
    state.errors.append({"node": "metrics_tool_node", "error": "database timeout"})

    report = FallbackService().generate_diagnosis_report(state)

    assert "数据分析失败原因：database timeout" in report
    assert "未检索到足够知识证据" in report
    assert "优化建议" in report
