"""Tests for optional LangGraph runner support."""

import app.agent.graph as graph_module
import pytest
from app.agent.graph import (
    build_langgraph,
    dict_to_state,
    run_agent,
    run_agent_langgraph,
    state_to_dict,
)
from app.config import get_settings
from app.db.init_db import initialize_database


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Keep AGENT_RUNNER env changes isolated between tests."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_run_agent_default_sequential(monkeypatch) -> None:
    """Default configuration should keep the stable sequential runner."""

    monkeypatch.setenv("AGENT_RUNNER", "sequential")
    get_settings.cache_clear()
    initialize_database()

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert result["runner"] == "sequential"
    assert result["final_answer"]
    assert all(span.get("runner") == "sequential" for span in result["node_spans"])


def test_build_langgraph_optional() -> None:
    """build_langgraph should not fail when optional dependency is absent."""

    graph = build_langgraph()

    assert graph is None or hasattr(graph, "invoke")


def test_langgraph_fallback_when_missing(monkeypatch) -> None:
    """Requested LangGraph mode should safely fall back when build returns None."""

    monkeypatch.setenv("AGENT_RUNNER", "langgraph")
    monkeypatch.setattr(graph_module, "build_langgraph", lambda: None)
    get_settings.cache_clear()
    initialize_database()

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert result["runner"] == "sequential"
    assert result["final_answer"]
    assert result["tool_results"]["runner_fallback"]["requested_runner"] == "langgraph"


def test_langgraph_runner_with_fake_graph(monkeypatch) -> None:
    """run_agent_langgraph should handle dict state returned by a compiled graph."""

    class FakeCompiledGraph:
        def invoke(self, data: dict, **kwargs: object) -> dict:
            state = dict_to_state(data)
            state.intent = "business_diagnosis"
            state.entity_id = "P1001"
            state.tool_results["fake_graph"] = {"ok": True}
            state.tool_results["fake_invoke_kwargs"] = kwargs
            state.final_answer = "fake langgraph final answer"
            return state_to_dict(state)

    monkeypatch.setattr(graph_module, "build_langgraph", lambda: FakeCompiledGraph())
    monkeypatch.setenv("LANGGRAPH_CHECKPOINT", "memory")
    initialize_database()
    get_settings.cache_clear()

    result = run_agent_langgraph("商品 P1001 最近 GMV 为什么下降？")

    assert result["runner"] == "langgraph"
    assert result["final_answer"] == "fake langgraph final answer"
    assert result["tool_results"]["fake_graph"]["ok"] is True
    assert result["tool_results"]["langgraph_runtime"]["checkpoint"] == "memory"
    assert result["tool_results"]["langgraph_runtime"]["logical_subgraphs"]
    assert "config" in result["tool_results"]["fake_invoke_kwargs"]


@pytest.mark.integration
def test_langgraph_runner_integration_when_installed() -> None:
    """When LangGraph is installed, the optional runner should execute end to end."""

    pytest.importorskip("langgraph")
    initialize_database()

    result = run_agent_langgraph("商品 P1001 最近 GMV 为什么下降？")

    assert result["runner"] == "langgraph"
    assert result["final_answer"]
    assert result["tool_results"]
    assert result["retrieved_docs"]
    assert result["node_spans"]
    assert all(span.get("runner") == "langgraph" for span in result["node_spans"])
