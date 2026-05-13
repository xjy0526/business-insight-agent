"""Node functions for the BusinessInsight Agent state machine."""

from __future__ import annotations

import re
from typing import Any

from app.agent.prompts import INTENT_ROUTER_PROMPT, PLANNER_PROMPT
from app.agent.state import AgentState, _now_iso
from app.db.database import get_connection
from app.services.fallback_service import FallbackService
from app.services.llm_service import LLMService
from app.services.report_service import ReportService
from app.tools.metrics_tool import (
    analyze_channel_breakdown,
    calculate_aov,
    calculate_gmv,
    calculate_refund_rate,
    calculate_traffic_metrics,
    compare_periods,
    get_product_basic_info,
)
from app.tools.rag_tool import search_business_knowledge

DEFAULT_TIME_RANGE = {
    "current_start": "2026-04-01",
    "current_end": "2026-04-30",
    "baseline_start": "2026-03-01",
    "baseline_end": "2026-03-31",
}


def _append_error(state: AgentState, node: str, error: Exception) -> None:
    """Record a node error without losing the trace."""

    state.errors.append({"node": node, "error": str(error)})


def _extract_product_id_from_query(query: str) -> str:
    """Map explicit product IDs or known product names to product_id."""

    product_ids = _extract_product_ids_from_query(query)
    if product_ids:
        return product_ids[0]

    compact_query = query.replace(" ", "")
    try:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT product_id, product_name FROM products"
            ).fetchall()
    except Exception:
        return ""

    for row in rows:
        product_name = str(row["product_name"])
        if product_name in query or product_name.replace(" ", "") in compact_query:
            return str(row["product_id"])

    return ""


def _extract_product_ids_from_query(query: str) -> list[str]:
    """Extract all explicit product IDs from a user query."""

    product_ids = re.findall(r"\bP\d{4}\b", query.upper())
    deduped_ids: list[str] = []
    for product_id in product_ids:
        if product_id not in deduped_ids:
            deduped_ids.append(product_id)
    return deduped_ids


def _infer_intent_from_query(query: str, entity_id: str) -> tuple[str, str, list[str]]:
    """Apply lightweight rules when mock LLM output is incomplete."""

    normalized_query = query.upper()
    business_terms = ("经营表现", "经营分析", "经营异常", "活动", "价格竞争力")
    traffic_terms = ("点击率", "转化率")
    if "差评" in query or "评价" in query:
        return (
            "review_analysis",
            "review",
            ["search_business_knowledge"],
        )
    if "GMV" in normalized_query or any(term in query for term in business_terms):
        return (
            "business_diagnosis",
            "gmv",
            [
                "get_product_basic_info",
                "compare_periods",
                "analyze_channel_breakdown",
                "search_business_knowledge",
            ],
        )
    if "退款率" in query:
        return (
            "refund_analysis",
            "refund_rate",
            ["calculate_refund_rate", "search_business_knowledge"],
        )
    if (
        any(term in query for term in traffic_terms)
        or "CTR" in normalized_query
        or "CVR" in normalized_query
    ):
        metric = "ctr" if "点击率" in query or "CTR" in normalized_query else "cvr"
        return (
            "traffic_analysis",
            metric,
            [
                "calculate_traffic_metrics",
                "analyze_channel_breakdown",
                "search_business_knowledge",
            ],
        )

    return (
        "unknown",
        "unknown",
        ["search_business_knowledge"] if entity_id else [],
    )


def _metric_change(
    comparison: dict[str, Any],
    metric_name: str,
) -> dict[str, Any]:
    """Return a metric change record from compare_periods output."""

    return comparison.get("changes", {}).get(
        metric_name,
        {"current": 0, "baseline": 0, "absolute_change": 0, "percent_change": None},
    )


def intent_router_node(state: AgentState) -> AgentState:
    """Recognize intent, entity, metric, time range, and required tools."""

    try:
        llm = LLMService()
        prompt = INTENT_ROUTER_PROMPT.format(query=state.user_query)
        result = llm.generate_json(prompt)

        entity_id = result.get("entity_id") or _extract_product_id_from_query(state.user_query)
        if not entity_id:
            entity_id = _extract_product_id_from_query(state.user_query)

        intent = result.get("intent", "")
        metric = result.get("metric", "")
        need_tools = result.get("need_tools", [])
        if intent in {"", "unknown"} or metric in {"", "unknown"}:
            intent, metric, need_tools = _infer_intent_from_query(state.user_query, entity_id)

        state.intent = intent
        state.entity_type = "product" if entity_id else result.get("entity_type", "unknown")
        state.entity_id = entity_id
        state.related_entity_ids = [
            product_id
            for product_id in _extract_product_ids_from_query(state.user_query)
            if product_id != entity_id
        ]
        state.metric = metric
        state.time_range = result.get("time_range") or DEFAULT_TIME_RANGE.copy()
        state.tool_results["intent_router"] = {
            "need_tools": need_tools,
            "raw_result": result,
        }
    except Exception as error:
        _append_error(state, "intent_router_node", error)

    return state


def planner_node(state: AgentState) -> AgentState:
    """Generate executable plan steps from intent and user query."""

    try:
        llm = LLMService()
        prompt = PLANNER_PROMPT.format(query=state.user_query, intent=state.intent)
        result = llm.generate_json(prompt)
        plan_steps = result.get("plan_steps", [])
        if not plan_steps:
            plan_steps = [
                {"step_id": 1, "name": "计算指标变化", "tool": "compare_periods"},
                {"step_id": 2, "name": "检索业务知识", "tool": "search_business_knowledge"},
                {"step_id": 3, "name": "生成诊断报告", "tool": "diagnosis_generator"},
            ]
        state.plan_steps = plan_steps
    except Exception as error:
        _append_error(state, "planner_node", error)

    return state


def metrics_tool_node(state: AgentState) -> AgentState:
    """Call metric tools for supported business intents."""

    if state.intent not in {"business_diagnosis", "refund_analysis", "traffic_analysis"}:
        return state

    if not state.entity_id:
        state.errors.append({"node": "metrics_tool_node", "error": "Missing product entity_id."})
        return state

    try:
        time_range = {**DEFAULT_TIME_RANGE, **state.time_range}
        current_start = time_range["current_start"]
        current_end = time_range["current_end"]
        baseline_start = time_range["baseline_start"]
        baseline_end = time_range["baseline_end"]

        product_basic_info = get_product_basic_info(state.entity_id)
        state.tool_results["product_basic_info"] = product_basic_info
        if not product_basic_info.get("found"):
            state.errors.append(
                {
                    "node": "metrics_tool_node",
                    "error": f"product_id not found: {state.entity_id}",
                }
            )
            return state

        state.tool_results["period_comparison"] = compare_periods(
            state.entity_id,
            current_start,
            current_end,
            baseline_start,
            baseline_end,
        )
        state.tool_results["current_gmv"] = calculate_gmv(
            state.entity_id,
            current_start,
            current_end,
        )
        state.tool_results["baseline_gmv"] = calculate_gmv(
            state.entity_id,
            baseline_start,
            baseline_end,
        )
        state.tool_results["current_traffic"] = calculate_traffic_metrics(
            state.entity_id,
            current_start,
            current_end,
        )
        state.tool_results["baseline_traffic"] = calculate_traffic_metrics(
            state.entity_id,
            baseline_start,
            baseline_end,
        )
        state.tool_results["current_refund"] = calculate_refund_rate(
            state.entity_id,
            current_start,
            current_end,
        )
        state.tool_results["baseline_refund"] = calculate_refund_rate(
            state.entity_id,
            baseline_start,
            baseline_end,
        )
        state.tool_results["current_aov"] = calculate_aov(
            state.entity_id,
            current_start,
            current_end,
        )
        state.tool_results["baseline_aov"] = calculate_aov(
            state.entity_id,
            baseline_start,
            baseline_end,
        )
        state.tool_results["current_channel_breakdown"] = analyze_channel_breakdown(
            state.entity_id,
            current_start,
            current_end,
        )
        state.tool_results["baseline_channel_breakdown"] = analyze_channel_breakdown(
            state.entity_id,
            baseline_start,
            baseline_end,
        )
        if state.related_entity_ids:
            state.tool_results["peer_period_comparisons"] = {
                product_id: compare_periods(
                    product_id,
                    current_start,
                    current_end,
                    baseline_start,
                    baseline_end,
                )
                for product_id in state.related_entity_ids
                if get_product_basic_info(product_id).get("found")
            }
    except Exception as error:
        _append_error(state, "metrics_tool_node", error)

    return state


def rag_retriever_node(state: AgentState) -> AgentState:
    """Retrieve knowledge evidence based on query and metric signals."""

    fallback = FallbackService()
    try:
        retrieval_terms = [state.user_query, state.intent, state.metric]
        comparison = state.tool_results.get("period_comparison", {})
        if comparison:
            gmv_change = _metric_change(comparison, "gmv")
            ctr_change = _metric_change(comparison, "ctr")
            refund_change = _metric_change(comparison, "refund_rate")
            if gmv_change.get("absolute_change", 0) < 0:
                retrieval_terms.append("GMV下降 活动 价格竞争力 转化率")
            if ctr_change.get("absolute_change", 0) < 0:
                retrieval_terms.append("点击率下降 主图 标题 搜索")
            if refund_change.get("absolute_change", 0) > 0:
                retrieval_terms.append("退款率升高 物流慢 差评 续航 佩戴不舒服")

        query = " ".join(retrieval_terms)
        result = fallback.normalize_rag_result(search_business_knowledge(query), query)
        state.retrieved_docs = result["results"]
        state.tool_results["rag_search"] = {
            "query": result["query"],
            "evidence_summary": result["evidence_summary"],
        }
    except Exception as error:
        _append_error(state, "rag_retriever_node", error)
        fallback_result = fallback.normalize_rag_result(None, state.user_query)
        state.retrieved_docs = fallback_result["results"]
        state.tool_results["rag_search"] = {
            "query": fallback_result["query"],
            "evidence_summary": fallback_result["evidence_summary"],
        }

    return state


def diagnosis_generator_node(state: AgentState) -> AgentState:
    """Generate a structured business diagnosis report."""

    try:
        state.diagnosis = ReportService().generate_diagnosis(state)
    except Exception as error:
        _append_error(state, "diagnosis_generator_node", error)
        state.diagnosis = FallbackService().generate_diagnosis_report(state)

    return state


def reflection_checker_node(state: AgentState) -> AgentState:
    """Check whether the diagnosis has key sections and enough evidence."""

    required_sections = ["问题概述", "指标拆解", "主要归因", "证据来源", "优化建议"]
    issues = [
        f"诊断报告缺少“{section}”部分。"
        for section in required_sections
        if section not in state.diagnosis
    ]

    if not state.tool_results:
        issues.append("缺少指标工具调用结果。")
    if not state.retrieved_docs:
        issues.append("缺少 RAG 检索证据。")

    suggestions = []
    if "缺少指标工具调用结果。" in issues:
        suggestions.append("补充 compare_periods、analyze_channel_breakdown 等指标工具调用。")
    if "缺少 RAG 检索证据。" in issues:
        suggestions.append("补充 search_business_knowledge 检索活动、售后、运营和评价知识。")

    state.reflection_result = {
        "pass": not issues,
        "issues": issues,
        "suggestions": suggestions,
    }
    return state


def final_report_node(state: AgentState) -> AgentState:
    """Build the final answer with trace and execution summary."""

    if not state.diagnosis:
        state.diagnosis = FallbackService().generate_diagnosis_report(state)

    state.finished_at = _now_iso()
    step_summary = "\n".join(
        (
            f"- {step.get('step_id', index)}. {step.get('name', '未命名步骤')}："
            f"{step.get('tool', '未指定工具')}"
        )
        for index, step in enumerate(state.plan_steps, start=1)
    )
    reflection_text = (
        "通过" if state.reflection_result.get("pass") else "未通过，需关注："
        + "；".join(state.reflection_result.get("issues", []))
    )

    state.final_answer = (
        f"{state.diagnosis}\n\n"
        f"---\n"
        f"trace_id: {state.trace_id}\n"
        f"执行步骤摘要：\n{step_summary}\n"
        f"反思校验：{reflection_text}"
    )
    return state
