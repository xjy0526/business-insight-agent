"""Sequential state-machine runner for BusinessInsight Agent."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.agent.nodes import (
    diagnosis_generator_node,
    final_report_node,
    intent_router_node,
    metrics_tool_node,
    planner_node,
    rag_retriever_node,
    reflection_checker_node,
)
from app.agent.state import AgentState, _now_iso
from app.services.trace_service import TraceService

AgentNode = Callable[[AgentState], AgentState]


def _summarize_state(state: AgentState) -> dict[str, Any]:
    """Return a compact state summary suitable for trace spans."""

    return {
        "intent": state.intent,
        "entity_id": state.entity_id,
        "related_entity_ids": state.related_entity_ids,
        "metric": state.metric,
        "plan_step_count": len(state.plan_steps),
        "tool_result_keys": sorted(state.tool_results.keys()),
        "retrieved_docs_count": len(state.retrieved_docs),
        "error_count": len(state.errors),
    }


def _run_node_with_span(node: AgentNode, state: AgentState) -> AgentState:
    """Run one node and append a per-node observability span."""

    input_summary = _summarize_state(state)
    error_type: str | None = None
    error_count_before = len(state.errors)
    started_at = perf_counter()

    try:
        state = node(state)
    except Exception as error:
        error_type = type(error).__name__
        state.errors.append({"node": node.__name__, "error": str(error)})

    if error_type is None and len(state.errors) > error_count_before:
        error_type = state.errors[-1].get("node", "node_error")

    latency_ms = int((perf_counter() - started_at) * 1000)
    state.node_spans.append(
        {
            "node": node.__name__,
            "latency_ms": latency_ms,
            "input_summary": input_summary,
            "output_summary": _summarize_state(state),
            "error_type": error_type,
        }
    )
    return state


def run_agent(
    query: str,
    cache_key: str | None = None,
    cache_hit: bool = False,
) -> dict:
    """Run the BusinessInsight Agent with a lightweight sequential graph."""

    started_at = perf_counter()
    state = AgentState(
        trace_id=str(uuid4()),
        user_query=query,
        cache_key=cache_key,
        cache_hit=cache_hit,
    )
    nodes = [
        intent_router_node,
        planner_node,
        metrics_tool_node,
        rag_retriever_node,
        diagnosis_generator_node,
        reflection_checker_node,
        final_report_node,
    ]
    unexpected_error_type: str | None = None

    try:
        for node in nodes:
            state = _run_node_with_span(node, state)
    except Exception as error:
        unexpected_error_type = type(error).__name__
        state.errors.append({"node": "run_agent", "error": str(error)})

    if state.finished_at is None:
        state.finished_at = _now_iso()
    if not state.final_answer:
        state.final_answer = (
            f"## 问题概述\nAgent 执行未生成完整诊断报告。\n\n"
            f"## 证据来源\n当前 trace 已保存，trace_id: {state.trace_id}\n\n"
            f"## 优化建议\n请检查 errors 字段并补充必要工具调用。"
        )

    latency_ms = int((perf_counter() - started_at) * 1000)
    error_type = unexpected_error_type
    if error_type is None and state.errors:
        error_type = state.errors[0].get("node", "agent_error")

    try:
        TraceService().save_trace(state, latency_ms=latency_ms, error_type=error_type)
    except Exception as error:
        state.errors.append({"node": "trace_service.save_trace", "error": str(error)})

    result = state.model_dump()
    result["latency_ms"] = latency_ms
    return result


def build_langgraph():
    """Reserved LangGraph adapter.

    后续如果引入 LangGraph，可以将当前顺序节点注册为 graph nodes，
    并用条件边实现 reflection 后的补充工具调用与重试。
    """

    return None
