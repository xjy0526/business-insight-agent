"""Rule-based evaluation metrics for BusinessInsight Agent."""

from __future__ import annotations

import json
from typing import Any

PRODUCT_AD_INTENTS = {
    "product_ad_strategy",
    "sku_mining",
    "sku_recall",
    "bid_recommendation",
    "poi_vs_product_ad_comparison",
}


def _answer_text(agent_result: dict[str, Any]) -> str:
    """Return final answer text from an agent result."""

    return agent_result.get("final_answer") or agent_result.get("answer") or ""


def _combined_result_text(agent_result: dict[str, Any]) -> str:
    """Return answer plus structured tool payloads for rule checks."""

    payload = {
        "tool_results": agent_result.get("tool_results", {}),
        "ad_results": agent_result.get("ad_results", {}),
        "recommendation_result": agent_result.get("recommendation_result", {}),
        "retrieved_docs": agent_result.get("retrieved_docs", []),
    }
    return _answer_text(agent_result) + "\n" + json.dumps(payload, ensure_ascii=False)


def check_intent_accuracy(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return 1.0 when the predicted intent matches the expected intent."""

    return 1.0 if agent_result.get("intent") == eval_case.get("expected_intent") else 0.0


def check_keyword_coverage(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return the share of expected keywords found in the final answer."""

    expected_keywords = eval_case.get("expected_keywords", [])
    if not expected_keywords:
        return 1.0

    answer = _answer_text(agent_result)
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
        "gmv_decomposition",
        "gmv_contribution",
    }

    used_tool_groups = set()
    if metric_keys.intersection(tool_results):
        used_tool_groups.add("metrics_tool")
    if retrieved_docs or "rag_search" in tool_results:
        used_tool_groups.add("rag_tool")
    if "review_analysis" in tool_results or "review_topic_analysis" in tool_results:
        used_tool_groups.add("review_tool")
    if "campaign_participation" in tool_results or "campaign_analysis" in tool_results:
        used_tool_groups.add("campaign_tool")
    if "product_ad" in tool_results or agent_result.get("ad_results"):
        used_tool_groups.add("product_ad_tool")

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

    answer = _answer_text(agent_result)
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

    answer = _answer_text(agent_result)
    query = eval_case.get("query", "")
    if query:
        answer = answer.replace(query, "")
    return 0.0 if any(keyword in answer for keyword in forbidden_keywords) else 1.0


def check_reflection_quality(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Score whether reflection_result contains supported claim-level evidence checks."""

    reflection_result = agent_result.get("reflection_result", {})
    if not reflection_result:
        return 0.0

    claim_checks = reflection_result.get("claim_checks", [])
    if not claim_checks:
        return 0.2

    score = 0.4
    expected_claim_types = eval_case.get("expected_claim_types", [])
    if expected_claim_types:
        supported_types = {
            check.get("claim_type")
            for check in claim_checks
            if check.get("supported")
        }
        matched_count = sum(
            1 for claim_type in expected_claim_types if claim_type in supported_types
        )
        score += 0.4 * round(matched_count / len(expected_claim_types), 6)
    else:
        supported_count = sum(1 for check in claim_checks if check.get("supported"))
        score += 0.4 * round(supported_count / len(claim_checks), 6)

    confidence = reflection_result.get("overall_confidence")
    if confidence == "high":
        score += 0.2
    elif confidence == "medium":
        score += 0.1

    forbidden_terms = (
        reflection_result.get("unsupported_absolute_claims", {}).get(
            "forbidden_terms_found",
            [],
        )
    )
    if forbidden_terms:
        score -= 0.3

    return round(min(max(score, 0.0), 1.0), 6)


def check_security_flags(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Return whether expected prompt/RAG security risks were recorded."""

    if not eval_case.get("expected_security_risk"):
        return 1.0

    tool_results = agent_result.get("tool_results", {})
    prompt_guard = tool_results.get("prompt_guard", {})
    security = tool_results.get("security", {})
    rag_security = tool_results.get("rag_security", {})
    errors = agent_result.get("errors", [])

    security_records = [prompt_guard, security, rag_security]
    for record in security_records:
        if not isinstance(record, dict):
            continue
        if record.get("is_injection"):
            return 1.0
        if record.get("risk_level") in {"medium", "high"}:
            return 1.0
        nested_prompt = record.get("prompt_injection", {})
        if isinstance(nested_prompt, dict) and nested_prompt.get("is_injection"):
            return 1.0
        nested_rag = record.get("rag_security", {})
        if isinstance(nested_rag, dict) and nested_rag.get("risk_level") in {
            "medium",
            "high",
        }:
            return 1.0

    error_text = " ".join(str(error) for error in errors).lower()
    return 1.0 if "security" in error_text or "prompt injection" in error_text else 0.0


def check_ad_recommendation_fields(
    agent_result: dict[str, Any],
    eval_case: dict[str, Any],
) -> float:
    """Check product-ad recommendation fields for strategy and mining cases."""

    if eval_case.get("expected_intent") not in {"product_ad_strategy", "sku_mining"}:
        return 1.0

    combined = _combined_result_text(agent_result)
    checks = [
        ("product_id", "P" in combined),
        ("product_name", "product_name" in combined or "套餐" in combined),
        ("product_growth_score", "product_growth_score" in combined or "final_score" in combined),
        ("CVR", "CVR" in combined or '"cvr"' in combined),
        ("GMV占比", "GMV占比" in combined or "gmv_share" in combined),
        ("PCVR", "PCVR" in combined or "pcvr" in combined),
        ("ROI", "ROI" in combined or "historical_roi" in combined),
        ("risk_flags", "risk_flags" in combined or "风险" in combined),
    ]
    matched = sum(1 for _, passed in checks if passed)
    return round(matched / len(checks), 6)


def check_bid_guardrail(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Check bid recommendation output for ROI guardrail fields."""

    if eval_case.get("expected_intent") != "bid_recommendation":
        return 1.0

    combined = _combined_result_text(agent_result)
    checks = [
        "target_roi" in combined or "目标 ROI" in combined,
        "max_cpc" in combined or "recommended_cpc_range" in combined or "出价区间" in combined,
        "PCVR" in combined or "pcvr" in combined,
        "price" in combined or "售价" in combined,
        "roi_status" in combined or "ROI 守护" in combined or "ROI guardrail" in combined,
    ]
    score = sum(1 for passed in checks if passed) / len(checks)
    if any(term in combined for term in ("risk", "低于目标", "退款率偏高", "roi_status\": \"risk")):
        cautious_terms = ("谨慎", "风险", "不建议盲目加价", "智能调价", "A/B测试")
        if not any(term in combined for term in cautious_terms):
            score -= 0.25
    return round(max(score, 0.0), 6)


def check_sku_recall_fields(agent_result: dict[str, Any], eval_case: dict[str, Any]) -> float:
    """Check Query-SKU recall output fields."""

    if eval_case.get("expected_intent") != "sku_recall":
        return 1.0

    combined = _combined_result_text(agent_result)
    checks = [
        "recall_path" in combined,
        "recall_score" in combined,
        "matched_terms" in combined,
        any(path in combined for path in ("keyword_inverted", "query_expansion", "vector_match")),
        "多路召回" in combined or "keyword_inverted" in combined,
    ]
    return round(sum(1 for passed in checks if passed) / len(checks), 6)


def check_poi_vs_product_comparison(
    agent_result: dict[str, Any],
    eval_case: dict[str, Any],
) -> float:
    """Check POI-level vs product-level comparison fields."""

    if eval_case.get("expected_intent") != "poi_vs_product_ad_comparison":
        return 1.0

    combined = _combined_result_text(agent_result)
    checks = [
        "POI级广告" in combined or "poi_level" in combined,
        "商品级广告" in combined or "product_level" in combined,
        "CTR" in combined or '"ctr"' in combined,
        "CVR" in combined or '"cvr"' in combined,
        "ROI" in combined or '"roi"' in combined,
        "对比" in combined or "相比" in combined,
    ]
    return round(sum(1 for passed in checks if passed) / len(checks), 6)


def check_claim_evidence_alignment(
    agent_result: dict[str, Any],
    eval_case: dict[str, Any],
) -> float:
    """Apply lightweight evidence alignment rules."""

    answer = _answer_text(agent_result)
    tool_results = agent_result.get("tool_results", {})
    retrieved_docs = agent_result.get("retrieved_docs", [])
    has_evidence = bool(tool_results or retrieved_docs or agent_result.get("ad_results"))
    strong_terms = ("明确", "一定", "必然", "唯一原因", "保证提升")
    score = 1.0
    if any(term in answer for term in strong_terms) and not has_evidence:
        score -= 0.5
    if eval_case.get("expected_intent") == "bid_recommendation":
        combined = _combined_result_text(agent_result)
        if "CPC" in answer and not any(term in combined for term in ("PCVR", "pcvr", "ROI")):
            score -= 0.5
    if eval_case.get("expected_intent") == "sku_recall":
        combined = _combined_result_text(agent_result)
        if "召回路径" in answer and "recall_path" not in combined:
            score -= 0.5
    return round(max(score, 0.0), 6)


def check_root_cause_or_recommendation_hit(
    agent_result: dict[str, Any],
    eval_case: dict[str, Any],
) -> float:
    """Check optional expected root causes or recommendations."""

    expected = eval_case.get("expected_root_causes") or eval_case.get("expected_recommendations")
    if not expected:
        return 1.0

    combined = _combined_result_text(agent_result)
    matched = sum(1 for item in expected if str(item) in combined)
    return round(matched / len(expected), 6)


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
    reflection_quality = check_reflection_quality(agent_result, eval_case)
    security_flag = check_security_flags(agent_result, eval_case)
    ad_recommendation_fields = check_ad_recommendation_fields(agent_result, eval_case)
    bid_guardrail = check_bid_guardrail(agent_result, eval_case)
    sku_recall_fields = check_sku_recall_fields(agent_result, eval_case)
    poi_vs_product_comparison = check_poi_vs_product_comparison(agent_result, eval_case)
    claim_evidence_alignment = check_claim_evidence_alignment(agent_result, eval_case)
    root_cause_or_recommendation_hit = check_root_cause_or_recommendation_hit(
        agent_result,
        eval_case,
    )
    score = (
        intent_accuracy * 0.15
        + keyword_coverage * 0.12
        + tool_usage * 0.12
        + evidence_hit * 0.10
        + entity_coverage * 0.08
        + tool_result_key_coverage * 0.08
        + ad_recommendation_fields * 0.10
        + bid_guardrail * 0.08
        + sku_recall_fields * 0.08
        + poi_vs_product_comparison * 0.04
        + claim_evidence_alignment * 0.03
        + forbidden_keyword_pass * 0.02
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
        "reflection_quality": reflection_quality,
        "security_flag": security_flag,
        "ad_recommendation_fields": ad_recommendation_fields,
        "bid_guardrail": bid_guardrail,
        "sku_recall_fields": sku_recall_fields,
        "poi_vs_product_comparison": poi_vs_product_comparison,
        "claim_evidence_alignment": claim_evidence_alignment,
        "root_cause_or_recommendation_hit": root_cause_or_recommendation_hit,
        "score": round(score, 6),
    }
