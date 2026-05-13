"""API tests for BusinessInsight Agent endpoints."""

import pytest
from app.db.init_db import initialize_database
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    """Ensure API tests run against a fresh local SQLite database."""

    initialize_database()


def test_agent_analyze_returns_answer() -> None:
    """The analyze endpoint should run the agent and return a diagnosis."""

    client = TestClient(app)
    response = client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"]
    assert data["intent"] == "business_diagnosis"
    assert "GMV" in data["answer"]
    assert data["tool_results"]
    assert data["retrieved_docs"]
    assert isinstance(data["latency_ms"], int)
    assert data["cache_key"]


def test_agent_analyze_can_bypass_cache() -> None:
    """use_cache=false should force a fresh Agent run."""

    client = TestClient(app)
    payload = {"query": "商品 P1001 最近 GMV 为什么下降？", "use_cache": False}

    first = client.post("/api/agent/analyze", json=payload)
    second = client.post("/api/agent/analyze", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is False
    assert first.json()["cache_key"] is None
    assert second.json()["cache_key"] is None
    assert first.json()["trace_id"] != second.json()["trace_id"]


def test_frontend_root_and_static_assets() -> None:
    """The demo frontend should be served by FastAPI."""

    client = TestClient(app)
    root_response = client.get("/")
    js_response = client.get("/static/app.js")

    assert root_response.status_code == 200
    assert "BusinessInsight Agent" in root_response.text
    assert js_response.status_code == 200
    assert "fetch(\"/api/agent/analyze\"" in js_response.text


def test_agent_analyze_rejects_empty_query() -> None:
    """Empty query should return a 400 error."""

    client = TestClient(app)
    response = client.post("/api/agent/analyze", json={"query": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "query cannot be empty."


def test_agent_analyze_returns_500_when_agent_fails(monkeypatch) -> None:
    """Unexpected Agent failures should be converted to a clear 500 response."""

    def failing_run_agent(query: str, cache_key: str | None = None) -> dict:
        raise RuntimeError("synthetic agent failure")

    monkeypatch.setattr("app.api.routes_agent.run_agent", failing_run_agent)
    client = TestClient(app)
    response = client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？", "use_cache": False},
    )

    assert response.status_code == 500
    assert "Agent execution failed: synthetic agent failure" in response.json()["detail"]


def test_metrics_compare_returns_result() -> None:
    """The metrics compare endpoint should return period comparison data."""

    client = TestClient(app)
    response = client.get(
        "/api/metrics/product/P1001/compare",
        params={
            "current_start": "2026-04-01",
            "current_end": "2026-04-30",
            "baseline_start": "2026-03-01",
            "baseline_end": "2026-03-31",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "P1001"
    assert "gmv" in data["changes"]


def test_metrics_compare_returns_404_for_unknown_product() -> None:
    """Unknown product IDs should return a clear API error."""

    client = TestClient(app)
    response = client.get(
        "/api/metrics/product/P9999/compare",
        params={
            "current_start": "2026-04-01",
            "current_end": "2026-04-30",
            "baseline_start": "2026-03-01",
            "baseline_end": "2026-03-31",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "product_id not found: P9999"


def test_metrics_compare_rejects_invalid_date_format() -> None:
    """Metric APIs should reject invalid date values before querying data."""

    client = TestClient(app)
    response = client.get(
        "/api/metrics/product/P1001/compare",
        params={
            "current_start": "2026/04/01",
            "current_end": "2026-04-30",
            "baseline_start": "2026-03-01",
            "baseline_end": "2026-03-31",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "current_start must use YYYY-MM-DD format."


def test_metrics_compare_rejects_reversed_date_range() -> None:
    """Metric APIs should reject start dates after end dates."""

    client = TestClient(app)
    response = client.get(
        "/api/metrics/product/P1001/compare",
        params={
            "current_start": "2026-04-30",
            "current_end": "2026-04-01",
            "baseline_start": "2026-03-01",
            "baseline_end": "2026-03-31",
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "current_start must be earlier than or equal to current_end."
    )


def test_trace_endpoints_return_saved_trace() -> None:
    """Trace endpoints should list and fetch persisted Agent traces."""

    client = TestClient(app)
    analyze_response = client.post(
        "/api/agent/analyze",
        json={"query": "商品 P1001 最近 GMV 为什么下降？"},
    )
    trace_id = analyze_response.json()["trace_id"]

    list_response = client.get("/api/traces", params={"limit": 5})
    get_response = client.get(f"/api/traces/{trace_id}")

    assert list_response.status_code == 200
    assert any(trace["trace_id"] == trace_id for trace in list_response.json())
    assert get_response.status_code == 200
    assert get_response.json()["trace_id"] == trace_id
    assert get_response.json()["node_spans"]


def test_eval_run_endpoint_returns_overall_metrics() -> None:
    """Eval endpoint should run cases and return aggregate metrics."""

    client = TestClient(app)
    response = client.post("/api/evals/run")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["case_count"] >= 5
    assert "avg_score" in data["overall_metrics"]
    assert len(data["case_results"]) >= 5
