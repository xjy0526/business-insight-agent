"""Rule-based evaluation metrics for BusinessInsight Agent."""

from __future__ import annotations

from typing import Any


def check_intent_accuracy(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return 1.0 when the predicted intent matches the expected intent."""

    return 1.0 if agent_result.get("intent") == eval_case.get("expected_intent") else 0.0


def check_keyword_coverage(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return the share of expected keywords found in the final answer."""

    expected_keywords = eval_case.get("expected_keywords", [])
    if not expected_keywords:
        return 1.0

    answer = agent_result.get("final_answer") or agent_result.get("answer") or ""
    matched = sum(1 for keyword in expected_keywords if keyword in answer)
    return round(matched / len(expected_keywords), 6)


def check_tool_usage(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return the share of expected tool groups used by the Agent."""

    expected_tools = eval_case.get("expected_tools", [])
    if not expected_tools:
        return 1.0

    tool_results = agent_result.get("tool_results", {})
    retrieved_docs = agent_result.get("retrieved_docs", [])
    metric_keys = {
        "product_basic_info",
        "period_comparison",
        "current_gmv",
        "baseline_gmv",
        "current_traffic",
        "baseline_traffic",
        "current_refund",
        "baseline_refund",
        "current_channel_breakdown",
        "baseline_channel_breakdown",
    }

    used_tool_groups = set()
    if metric_keys.intersection(tool_results):
        used_tool_groups.add("metrics_tool")
    if retrieved_docs or "rag_search" in tool_results:
        used_tool_groups.add("rag_tool")

    matched = sum(1 for tool_name in expected_tools if tool_name in used_tool_groups)
    return round(matched / len(expected_tools), 6)


def check_evidence_hit(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return 1.0 if at least one expected evidence source is retrieved."""

    expected_sources = set(eval_case.get("expected_evidence_sources", []))
    if not expected_sources:
        return 1.0

    retrieved_sources = {
        doc.get("source")
        for doc in agent_result.get("retrieved_docs", [])
        if doc.get("source")
    }
    return 1.0 if expected_sources.intersection(retrieved_sources) else 0.0


def check_entity_coverage(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return the share of expected product IDs recognized or mentioned."""

    expected_entities = eval_case.get("expected_entity_ids", [])
    if not expected_entities:
        return 1.0

    answer = agent_result.get("final_answer") or agent_result.get("answer") or ""
    observed_entities = {
        agent_result.get("entity_id"),
        *agent_result.get("related_entity_ids", []),
    }
    matched = sum(
        1
        for entity_id in expected_entities
        if entity_id in observed_entities or entity_id in answer
    )
    return round(matched / len(expected_entities), 6)


def check_tool_result_keys(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return the share of required tool result keys present in tool_results."""

    expected_keys = eval_case.get("expected_tool_result_keys", [])
    if not expected_keys:
        return 1.0

    tool_results = agent_result.get("tool_results", {})
    matched = sum(1 for key in expected_keys if key in tool_results)
    return round(matched / len(expected_keys), 6)


def check_trace_fields(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return the share of required trace/state fields present and non-empty."""

    expected_fields = eval_case.get("expected_trace_fields", [])
    if not expected_fields:
        return 1.0

    matched = sum(1 for field_name in expected_fields if agent_result.get(field_name))
    return round(matched / len(expected_fields), 6)


def check_error_expectations(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return whether expected error nodes appeared in state.errors."""

    expected_error_nodes = eval_case.get("expected_error_nodes", [])
    if not expected_error_nodes:
        return 1.0

    observed_nodes = {
        error.get("node")
        for error in agent_result.get("errors", [])
        if error.get("node")
    }
    return 1.0 if set(expected_error_nodes).issubset(observed_nodes) else 0.0


def check_forbidden_keywords(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return 1.0 when the answer avoids forbidden unsupported claims."""

    forbidden_keywords = eval_case.get("forbidden_keywords", [])
    if not forbidden_keywords:
        return 1.0

    answer = agent_result.get("final_answer") or agent_result.get("answer") or ""
    query = eval_case.get("query", "")
    if query:
        answer = answer.replace(query, "")
    return 0.0 if any(keyword in answer for keyword in forbidden_keywords) else 1.0


def calculate_case_score(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> dict[str, Any]:
    """Calculate component metrics and weighted score for one eval case."""

    intent_accuracy = check_intent_accuracy(agent_result, eval_case)
    keyword_coverage = check_keyword_coverage(agent_result, eval_case)
    tool_usage = check_tool_usage(agent_result, eval_case)
    evidence_hit = check_evidence_hit(agent_result, eval_case)
    entity_coverage = check_entity_coverage(agent_result, eval_case)
    tool_result_key_coverage = check_tool_result_keys(agent_result, eval_case)
    trace_field_coverage = check_trace_fields(agent_result, eval_case)
    error_expectation = check_error_expectations(agent_result, eval_case)
    forbidden_keyword_pass = check_forbidden_keywords(agent_result, eval_case)
    score = (
        intent_accuracy * 0.22
        + keyword_coverage * 0.18
        + tool_usage * 0.15
        + evidence_hit * 0.15
        + entity_coverage * 0.10
        + tool_result_key_coverage * 0.08
        + trace_field_coverage * 0.06
        + error_expectation * 0.03
        + forbidden_keyword_pass * 0.03
    )

    return {
        "intent_accuracy": intent_accuracy,
        "keyword_coverage": keyword_coverage,
        "tool_usage": tool_usage,
        "evidence_hit": evidence_hit,
        "entity_coverage": entity_coverage,
        "tool_result_key_coverage": tool_result_key_coverage,
        "trace_field_coverage": trace_field_coverage,
        "error_expectation": error_expectation,
        "forbidden_keyword_pass": forbidden_keyword_pass,
        "score": round(score, 6),
    }
