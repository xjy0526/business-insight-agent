"""Agent runners for BusinessInsight Agent.

The default runner is a lightweight sequential/conditional state machine so the
project stays easy to run locally. LangGraph is supported as an optional adapter
and falls back to the sequential runner when the package is unavailable.
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any, Literal, TypedDict
from uuid import uuid4

from app.agent.nodes import (
    diagnosis_generator_node,
    final_report_node,
    intent_router_node,
    metrics_tool_node,
    planner_node,
    product_ad_tool_node,
    prompt_guard_node,
    rag_retriever_node,
    recommendation_scorer_node,
    reflection_checker_node,
)
from app.agent.state import AgentState, _now_iso
from app.config import get_settings
from app.services.trace_service import TraceService

AgentNode = Callable[[AgentState], AgentState]
RunnerName = Literal["sequential", "langgraph"]


class AgentGraphData(TypedDict, total=False):
    """TypedDict state schema used by the optional LangGraph adapter."""

    trace_id: str
    user_query: str
    safe_user_query: str
    security_flags: dict[str, Any]
    intent: str
    domain: str
    route_type: str
    entity_type: str
    entity_id: str
    related_entity_ids: list[str]
    metric: str
    time_range: dict[str, Any]
    plan_steps: list[dict[str, Any]]
    tool_results: dict[str, Any]
    ad_results: dict[str, Any]
    recommendation_result: dict[str, Any]
    evidence_alignment: dict[str, Any]
    retrieved_docs: list[dict[str, Any]]
    diagnosis: str
    reflection_result: dict[str, Any]
    final_answer: str
    errors: list[dict[str, str]]
    node_spans: list[dict[str, Any]]
    cache_key: str | None
    cache_hit: bool
    controls: dict[str, Any]
    disabled_components: list[str]
    retry_count: int
    runner: str
    started_at: str
    finished_at: str | None


CONTROL_COMPONENT_MAP = {
    "disable_rag": ["rag"],
    "disable_metrics": ["metrics"],
    "disable_product_ad": ["product_ad"],
    "disable_review_campaign": ["review", "campaign"],
    "disable_reflection": ["reflection"],
    "mock_only": [
        "metrics",
        "product_ad",
        "rag",
        "review",
        "campaign",
        "reflection",
        "evidence_repair",
    ],
}

TOOL_ROUTED_INTENTS = {
    "business_diagnosis",
    "refund_analysis",
    "traffic_analysis",
    "review_analysis",
}
PRODUCT_AD_ROUTED_INTENTS = {
    "product_ad_strategy",
    "sku_mining",
    "sku_recall",
    "bid_recommendation",
    "poi_vs_product_ad_comparison",
}
LANGGRAPH_VISUAL_EDGES = [
    {"from": "START", "to": "prompt_guard", "condition": "always"},
    {"from": "prompt_guard", "to": "intent_router", "condition": "always"},
    {"from": "intent_router", "to": "planner", "condition": "always"},
    {"from": "planner", "to": "tool_router", "condition": "always"},
    {"from": "tool_router", "to": "metrics_tool", "condition": "known intent + entity"},
    {"from": "tool_router", "to": "product_ad_tool", "condition": "product ad intent"},
    {"from": "tool_router", "to": "rag_retriever", "condition": "unknown or missing entity"},
    {"from": "product_ad_tool", "to": "rag_retriever", "condition": "always"},
    {"from": "metrics_tool", "to": "rag_retriever", "condition": "always"},
    {"from": "rag_retriever", "to": "recommendation_scorer", "condition": "always"},
    {"from": "recommendation_scorer", "to": "diagnosis_generator", "condition": "always"},
    {"from": "diagnosis_generator", "to": "reflection_checker", "condition": "always"},
    {"from": "reflection_checker", "to": "evidence_retry", "condition": "fail and retry_count < 1"},
    {"from": "reflection_checker", "to": "final_report", "condition": "pass or retry exhausted"},
    {"from": "evidence_retry", "to": "rag_retriever", "condition": "always"},
    {"from": "final_report", "to": "END", "condition": "always"},
]
LANGGRAPH_SUBGRAPHS = [
    {
        "name": "tool_selection_subgraph",
        "nodes": ["tool_router", "metrics_tool", "product_ad_tool", "rag_retriever"],
        "purpose": "route business queries to deterministic tools and evidence retrieval",
    },
    {
        "name": "reflection_repair_subgraph",
        "nodes": ["diagnosis_generator", "reflection_checker", "evidence_retry"],
        "purpose": "retry evidence retrieval once when claim-level support is insufficient",
    },
]


def state_to_dict(state: AgentState) -> dict[str, Any]:
    """Convert AgentState to a plain dict for LangGraph."""

    return state.model_dump()


def dict_to_state(data: dict[str, Any] | AgentState) -> AgentState:
    """Convert a LangGraph dict payload back to AgentState."""

    if isinstance(data, AgentState):
        return data
    return AgentState(**data)


def _normalize_controls(controls: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete Agent controls dictionary."""

    normalized = {
        "disable_rag": False,
        "disable_metrics": False,
        "disable_product_ad": False,
        "disable_review_campaign": False,
        "disable_reflection": False,
        "mock_only": False,
    }
    if controls:
        normalized.update({key: bool(value) for key, value in controls.items()})
    return normalized


def _disabled_components_from_controls(controls: dict[str, Any]) -> list[str]:
    """Map high-level Agent controls to disabled component names."""

    disabled_components: list[str] = []
    for control_name, component_names in CONTROL_COMPONENT_MAP.items():
        if controls.get(control_name):
            for component_name in component_names:
                if component_name not in disabled_components:
                    disabled_components.append(component_name)
    return disabled_components


def _summarize_state(state: AgentState) -> dict[str, Any]:
    """Return a compact state summary suitable for trace spans."""

    return {
        "runner": state.runner,
        "retry_count": state.retry_count,
        "intent": state.intent,
        "entity_id": state.entity_id,
        "related_entity_ids": state.related_entity_ids,
        "metric": state.metric,
        "domain": state.domain,
        "route_type": state.route_type,
        "security_risk": state.security_flags.get("risk_level"),
        "controls": state.controls,
        "disabled_components": state.disabled_components,
        "plan_step_count": len(state.plan_steps),
        "tool_result_keys": sorted(state.tool_results.keys()),
        "retrieved_docs_count": len(state.retrieved_docs),
        "error_count": len(state.errors),
    }


def _run_node_with_span(
    node: AgentNode,
    state: AgentState,
    graph_node: str | None = None,
) -> AgentState:
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
            "graph_node": graph_node or node.__name__,
            "runner": state.runner,
            "latency_ms": latency_ms,
            "input_summary": input_summary,
            "output_summary": _summarize_state(state),
            "error_type": error_type,
        }
    )
    return state


def _tool_router_node(state: AgentState) -> AgentState:
    """Record the selected tool route before conditional edges run."""

    route = _route_after_tool_router(state_to_dict(state))
    state.tool_results["graph_routing"] = {
        **state.tool_results.get("graph_routing", {}),
        "runner": state.runner,
        "tool_route": route,
        "retry_count": state.retry_count,
    }
    return state


def _evidence_retry_node(state: AgentState) -> AgentState:
    """Increment retry count before a LangGraph evidence-retrieval repair pass."""

    state.retry_count += 1
    state.tool_results["graph_routing"] = {
        **state.tool_results.get("graph_routing", {}),
        "evidence_repair_attempted": True,
        "retry_count": state.retry_count,
    }
    return state


def _langgraph_runtime_metadata() -> dict[str, Any]:
    """Return runtime metadata for checkpointing, subgraphs, and visual trace."""

    settings = get_settings()
    metadata: dict[str, Any] = {
        "checkpoint": settings.langgraph_checkpoint,
        "logical_subgraphs": LANGGRAPH_SUBGRAPHS,
    }
    if settings.langgraph_visual_trace:
        metadata["visual_trace_edges"] = LANGGRAPH_VISUAL_EDGES
    return metadata


def _langgraph_compile_kwargs() -> dict[str, Any]:
    """Build optional LangGraph compile kwargs without requiring checkpoint deps."""

    checkpoint_mode = get_settings().langgraph_checkpoint.lower()
    if checkpoint_mode not in {"memory", "in_memory"}:
        return {}
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        return {}
    return {"checkpointer": MemorySaver()}


def _langgraph_invoke_kwargs(state: AgentState) -> dict[str, Any]:
    """Return invoke kwargs required by optional checkpointing."""

    checkpoint_mode = get_settings().langgraph_checkpoint.lower()
    if checkpoint_mode not in {"memory", "in_memory"}:
        return {}
    return {"config": {"configurable": {"thread_id": state.trace_id}}}


def _route_after_tool_router(data: dict[str, Any]) -> str:
    """Route to metrics tools when intent and entity are sufficient."""

    state = dict_to_state(data)
    if state.intent in PRODUCT_AD_ROUTED_INTENTS:
        return "product_ad_tool"
    if state.intent in TOOL_ROUTED_INTENTS and state.entity_id:
        return "metrics_tool"
    return "rag_retriever"


def _route_after_reflection(data: dict[str, Any]) -> str:
    """Route after Reflection based on pass status and retry count."""

    state = dict_to_state(data)
    if state.reflection_result.get("pass"):
        return "final_report"
    if state.retry_count < 1 and "evidence_repair" not in state.disabled_components:
        return "evidence_retry"
    return "final_report"


def _langgraph_node_with_span(node_name: str, node: AgentNode) -> Callable[[dict[str, Any]], dict]:
    """Wrap existing AgentState nodes so LangGraph can execute dict state."""

    def wrapped(data: dict[str, Any]) -> dict[str, Any]:
        state = dict_to_state(data)
        state.runner = "langgraph"
        state = _run_node_with_span(node, state, graph_node=node_name)
        return state_to_dict(state)

    wrapped.__name__ = f"{node_name}_langgraph_wrapper"
    return wrapped


def _make_initial_state(
    query: str,
    cache_key: str | None,
    cache_hit: bool,
    disabled_components: list[str] | None,
    controls: dict[str, Any] | None,
    runner: RunnerName,
    fallback_reason: str | None = None,
) -> AgentState:
    """Create initial AgentState with controls and optional runner fallback info."""

    normalized_controls = _normalize_controls(controls)
    merged_disabled_components = [
        *list(disabled_components or []),
        *_disabled_components_from_controls(normalized_controls),
    ]
    merged_disabled_components = list(dict.fromkeys(merged_disabled_components))
    state = AgentState(
        trace_id=str(uuid4()),
        user_query=query,
        cache_key=cache_key,
        cache_hit=cache_hit,
        controls=normalized_controls,
        disabled_components=merged_disabled_components,
        runner=runner,
    )
    if fallback_reason:
        state.tool_results["runner_fallback"] = {
            "requested_runner": "langgraph",
            "fallback_runner": runner,
            "reason": fallback_reason,
        }
    return state


def _finalize_agent_state(
    state: AgentState,
    started_at: float,
    unexpected_error_type: str | None = None,
) -> dict[str, Any]:
    """Finalize, persist, and serialize an AgentState."""

    if state.finished_at is None:
        state.finished_at = _now_iso()
    if not state.final_answer:
        state.final_answer = (
            "## 问题概述\nAgent 执行未生成完整诊断报告。\n\n"
            f"## 证据来源\n当前 trace 已保存，trace_id: {state.trace_id}\n\n"
            "## 优化建议\n请检查 errors 字段并补充必要工具调用。"
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


class SequentialAgentGraph:
    """Lightweight conditional runner with no mandatory external dependency."""

    def __init__(self, engine: str = "sequential") -> None:
        self.engine = engine

    def run(self, state: AgentState) -> AgentState:
        """Run the sequential graph and conditionally add evidence-repair passes."""

        state.runner = "sequential"
        state.tool_results["graph_routing"] = {
            "engine": self.engine,
            "runner": state.runner,
            "disabled_components": state.disabled_components,
            "evidence_repair_attempted": False,
        }
        for node in [
            prompt_guard_node,
            intent_router_node,
            planner_node,
            metrics_tool_node,
            product_ad_tool_node,
            rag_retriever_node,
            recommendation_scorer_node,
            diagnosis_generator_node,
            reflection_checker_node,
        ]:
            state = _run_node_with_span(node, state)

        if self._needs_evidence_repair(state):
            state.retry_count += 1
            state.tool_results["graph_routing"]["evidence_repair_attempted"] = True
            state.tool_results["graph_routing"]["retry_count"] = state.retry_count
            for node in [
                rag_retriever_node,
                recommendation_scorer_node,
                diagnosis_generator_node,
                reflection_checker_node,
            ]:
                state = _run_node_with_span(node, state)

        return _run_node_with_span(final_report_node, state)

    def _needs_evidence_repair(self, state: AgentState) -> bool:
        """Return whether a second evidence pass is useful and safe."""

        if state.reflection_result.get("pass"):
            return False
        if state.retry_count >= 1:
            return False
        if "evidence_repair" in state.disabled_components:
            return False
        suggestions = " ".join(state.reflection_result.get("suggestions", []))
        return any(term in suggestions for term in ("search_business_knowledge", "RAG", "工具"))


def run_agent_sequential(
    query: str,
    cache_key: str | None = None,
    cache_hit: bool = False,
    disabled_components: list[str] | None = None,
    controls: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> dict:
    """Run the BusinessInsight Agent with the default sequential runner."""

    started_at = perf_counter()
    state = _make_initial_state(
        query=query,
        cache_key=cache_key,
        cache_hit=cache_hit,
        disabled_components=disabled_components,
        controls=controls,
        runner="sequential",
        fallback_reason=fallback_reason,
    )
    unexpected_error_type: str | None = None

    try:
        state = SequentialAgentGraph().run(state)
    except Exception as error:
        unexpected_error_type = type(error).__name__
        state.errors.append({"node": "run_agent_sequential", "error": str(error)})

    return _finalize_agent_state(state, started_at, unexpected_error_type)


def build_langgraph() -> Any | None:
    """Build a compiled LangGraph conditional graph when LangGraph is installed.

    Returns None when LangGraph is unavailable so callers can safely fall back to
    the sequential runner.
    """

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return None

    state_graph: Any = StateGraph
    graph: Any = state_graph(AgentGraphData)
    graph.add_node("prompt_guard", _langgraph_node_with_span("prompt_guard", prompt_guard_node))
    graph.add_node("intent_router", _langgraph_node_with_span("intent_router", intent_router_node))
    graph.add_node("planner", _langgraph_node_with_span("planner", planner_node))
    graph.add_node("tool_router", _langgraph_node_with_span("tool_router", _tool_router_node))
    graph.add_node("metrics_tool", _langgraph_node_with_span("metrics_tool", metrics_tool_node))
    graph.add_node(
        "product_ad_tool",
        _langgraph_node_with_span("product_ad_tool", product_ad_tool_node),
    )
    graph.add_node("rag_retriever", _langgraph_node_with_span("rag_retriever", rag_retriever_node))
    graph.add_node(
        "recommendation_scorer",
        _langgraph_node_with_span("recommendation_scorer", recommendation_scorer_node),
    )
    graph.add_node(
        "diagnosis_generator",
        _langgraph_node_with_span("diagnosis_generator", diagnosis_generator_node),
    )
    graph.add_node(
        "reflection_checker",
        _langgraph_node_with_span("reflection_checker", reflection_checker_node),
    )
    graph.add_node(
        "evidence_retry",
        _langgraph_node_with_span("evidence_retry", _evidence_retry_node),
    )
    graph.add_node("final_report", _langgraph_node_with_span("final_report", final_report_node))

    graph.add_edge(START, "prompt_guard")
    graph.add_edge("prompt_guard", "intent_router")
    graph.add_edge("intent_router", "planner")
    graph.add_edge("planner", "tool_router")
    graph.add_conditional_edges(
        "tool_router",
        _route_after_tool_router,
        {
            "metrics_tool": "metrics_tool",
            "product_ad_tool": "product_ad_tool",
            "rag_retriever": "rag_retriever",
        },
    )
    graph.add_edge("metrics_tool", "rag_retriever")
    graph.add_edge("product_ad_tool", "rag_retriever")
    graph.add_edge("rag_retriever", "recommendation_scorer")
    graph.add_edge("recommendation_scorer", "diagnosis_generator")
    graph.add_edge("diagnosis_generator", "reflection_checker")
    graph.add_conditional_edges(
        "reflection_checker",
        _route_after_reflection,
        {
            "evidence_retry": "evidence_retry",
            "final_report": "final_report",
        },
    )
    graph.add_edge("evidence_retry", "rag_retriever")
    graph.add_edge("final_report", END)
    return graph.compile(**_langgraph_compile_kwargs())


def run_agent_langgraph(
    query: str,
    cache_key: str | None = None,
    cache_hit: bool = False,
    disabled_components: list[str] | None = None,
    controls: dict[str, Any] | None = None,
) -> dict:
    """Run the Agent with the optional LangGraph adapter, falling back safely."""

    compiled_graph = build_langgraph()
    if compiled_graph is None:
        return run_agent_sequential(
            query=query,
            cache_key=cache_key,
            cache_hit=cache_hit,
            disabled_components=disabled_components,
            controls=controls,
            fallback_reason="LangGraph is not installed; using sequential runner.",
        )

    started_at = perf_counter()
    state = _make_initial_state(
        query=query,
        cache_key=cache_key,
        cache_hit=cache_hit,
        disabled_components=disabled_components,
        controls=controls,
        runner="langgraph",
    )
    state.tool_results["langgraph_runtime"] = _langgraph_runtime_metadata()
    unexpected_error_type: str | None = None

    try:
        invoke_kwargs = _langgraph_invoke_kwargs(state)
        try:
            output = compiled_graph.invoke(state_to_dict(state), **invoke_kwargs)
        except TypeError:
            output = compiled_graph.invoke(state_to_dict(state))
        state = dict_to_state(output)
        state.runner = "langgraph"
    except Exception as error:
        unexpected_error_type = type(error).__name__
        state.errors.append({"node": "run_agent_langgraph", "error": str(error)})
        state.tool_results["runner_fallback"] = {
            "requested_runner": "langgraph",
            "fallback_runner": "sequential",
            "reason": f"LangGraph execution failed: {type(error).__name__}",
        }
        fallback_result = run_agent_sequential(
            query=query,
            cache_key=cache_key,
            cache_hit=cache_hit,
            disabled_components=disabled_components,
            controls=controls,
            fallback_reason=f"LangGraph execution failed: {type(error).__name__}",
        )
        fallback_result.setdefault("errors", []).append(
            {"node": "run_agent_langgraph", "error": str(error)}
        )
        return fallback_result

    return _finalize_agent_state(state, started_at, unexpected_error_type)


def run_agent(
    query: str,
    cache_key: str | None = None,
    cache_hit: bool = False,
    disabled_components: list[str] | None = None,
    controls: dict[str, Any] | None = None,
) -> dict:
    """Run the BusinessInsight Agent using the configured runner."""

    runner = get_settings().agent_runner.lower()
    if runner == "langgraph":
        return run_agent_langgraph(
            query=query,
            cache_key=cache_key,
            cache_hit=cache_hit,
            disabled_components=disabled_components,
            controls=controls,
        )
    return run_agent_sequential(
        query=query,
        cache_key=cache_key,
        cache_hit=cache_hit,
        disabled_components=disabled_components,
        controls=controls,
    )
