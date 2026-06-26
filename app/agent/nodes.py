"""Node functions for the BusinessInsight Agent state machine."""

from __future__ import annotations

import re
from typing import Any

from app.agent.prompts import INTENT_ROUTER_PROMPT, PLANNER_PROMPT
from app.agent.state import AgentState, _now_iso
from app.db.database import get_connection
from app.services.evidence_checker import EvidenceChecker
from app.services.fallback_service import FallbackService
from app.services.llm_service import LLMService
from app.services.report_service import ReportService
from app.services.security_service import PromptInjectionGuard, SecurityService
from app.tools.campaign_tool import check_campaign_participation, compare_campaign_context
from app.tools.metrics_tool import (
    analyze_channel_breakdown,
    calculate_aov,
    calculate_gmv,
    calculate_refund_rate,
    calculate_traffic_metrics,
    compare_periods,
    decompose_gmv_change,
    get_product_basic_info,
)
from app.tools.product_ad_tool import (
    PRODUCT_AD_INTENTS,
    compare_poi_vs_product_ads,
    mine_high_value_products,
    rank_ad_candidates,
    recall_query_to_sku,
    recommend_bid_range,
    simulate_bid_strategy,
)
from app.tools.rag_tool import search_business_knowledge
from app.tools.review_tool import analyze_review_topics, compare_review_periods

DEFAULT_TIME_RANGE = {
    "current_start": "2026-04-01",
    "current_end": "2026-04-30",
    "baseline_start": "2026-03-01",
    "baseline_end": "2026-03-31",
}


def _append_error(state: AgentState, node: str, error: Exception) -> None:
    """Record a node error without losing the trace."""

    state.errors.append({"node": node, "error": str(error)})


def _effective_query(state: AgentState) -> str:
    """Return the prompt-guarded query when available."""

    return state.safe_user_query or state.user_query


def _record_llm_provider(state: AgentState, llm: LLMService) -> None:
    """Record trace-safe LLM provider metadata without credentials."""

    state.tool_results["llm_provider"] = llm.provider_metadata()


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


def _extract_merchant_id_from_query(query: str) -> str:
    """Extract a merchant ID such as M001 from text."""

    match = re.search(r"\bM\d{3}\b", query.upper())
    return match.group(0) if match else ""


def _extract_bid_multiplier_from_query(query: str) -> float:
    """Extract bid multiplier from phrases like 加价20%."""

    percent_match = re.search(r"(?:加价|提价|溢价|上调)\s*(\d+(?:\.\d+)?)\s*%", query)
    if percent_match:
        return round(1 + float(percent_match.group(1)) / 100, 3)
    multiplier_match = re.search(r"(?:bid_multiplier|出价倍数)\s*[:：=]?\s*(\d+(?:\.\d+)?)", query)
    if multiplier_match:
        return round(float(multiplier_match.group(1)), 3)
    return 1.2 if "加价" in query or "溢价" in query else 1.0


def _extract_target_roi_from_query(query: str) -> float:
    """Extract target ROI from natural-language query."""

    match = re.search(r"(?:目标\s*)?ROI\s*(?:为|=|:|：)?\s*(\d+(?:\.\d+)?)", query, re.I)
    if match:
        return float(match.group(1))
    return 3.0


def _extract_recall_query_from_user_query(query: str) -> str:
    """Extract the natural search query from recall-style questions."""

    patterns = [
        r"用户搜索\s*([^，,。?？\s]+)",
        r"搜索\s*([^，,。?？\s]+)",
        r"Query\s*(?:是|为|:|：)?\s*([^，,。?？\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.I)
        if match:
            return match.group(1).strip()
    known_queries = [
        "水光补水",
        "小气泡清洁",
        "美甲款式",
        "自然款美睫",
        "双人烤肉",
        "亲子摄影",
        "健身私教体验",
        "洗剪吹造型",
    ]
    for known_query in known_queries:
        if known_query in query:
            return known_query
    return query.strip()


def _is_product_ad_query(query: str) -> bool:
    """Return whether the query contains product-level ad decision language."""

    normalized_query = query.upper()
    ad_terms = (
        "广告",
        "投放",
        "主推品",
        "爆品",
        "加价",
        "出价",
        "智能调价",
        "商品级",
        "门店级",
        "POI",
        "PCVR",
        "CPC",
        "ROI",
        "SKU",
        "QUERY",
        "召回",
        "关键词",
        "搜索词",
        "匹配",
    )
    local_service_terms = (
        "水光补水",
        "小气泡清洁",
        "美甲款式",
        "自然款美睫",
        "双人烤肉",
        "亲子摄影",
        "健身私教体验",
        "洗剪吹造型",
    )
    return any(term in normalized_query or term in query for term in ad_terms) or any(
        term in query for term in local_service_terms
    )


def _infer_product_ad_intent_from_query(query: str) -> tuple[str, str, list[str]]:
    """Infer product-level advertising intents with deterministic rules."""

    normalized_query = query.upper()
    comparison_terms = ("POI", "门店级", "商品级广告相比", "升级到商品级")
    recall_terms = (
        "召回",
        "SKU",
        "QUERY",
        "关键词",
        "搜索词",
        "匹配",
        "用户搜索",
        "水光补水",
        "美甲款式",
        "双人烤肉",
        "小气泡清洁",
        "自然款美睫",
        "健身私教体验",
        "洗剪吹造型",
    )
    bid_terms = (
        "出价",
        "CPC",
        "ROI",
        "加价",
        "溢价",
        "智能调价",
        "最高可接受",
        "BID",
    )
    sku_mining_terms = (
        "哪些商品",
        "哪些团购",
        "主推品",
        "爆品",
        "挖品",
        "优先推",
        "适合作为",
        "适合做商品级广告",
        "预算有限",
        "高 CVR",
        "高GMV",
        "GMV 占比",
        "GMV占比",
    )

    if any(term in normalized_query or term in query for term in comparison_terms):
        return (
            "poi_vs_product_ad_comparison",
            "ad_performance",
            ["compare_poi_vs_product_ads", "search_business_knowledge"],
        )
    if any(term in normalized_query or term in query for term in recall_terms):
        return (
            "sku_recall",
            "query_sku_recall",
            ["recall_query_to_sku", "rank_ad_candidates", "search_business_knowledge"],
        )
    if (
        "退款率" in query
        and "主推品" in query
        and not any(term in normalized_query or term in query for term in ("CPC", "ROI", "出价"))
    ):
        return (
            "product_ad_strategy",
            "product_ad_priority",
            ["mine_high_value_products", "rank_ad_candidates", "search_business_knowledge"],
        )
    if any(term in normalized_query or term in query for term in bid_terms):
        return (
            "bid_recommendation",
            "roi_guardrail",
            ["recommend_bid_range", "simulate_bid_strategy", "search_business_knowledge"],
        )
    if any(term in query for term in sku_mining_terms):
        intent = "sku_mining" if "哪些团购" in query or "挖品" in query else "product_ad_strategy"
        return (
            intent,
            "product_growth_score",
            ["mine_high_value_products", "rank_ad_candidates", "search_business_knowledge"],
        )
    if _is_product_ad_query(query):
        return (
            "product_ad_strategy",
            "product_ad_priority",
            ["mine_high_value_products", "rank_ad_candidates", "search_business_knowledge"],
        )
    return ("unknown", "unknown", [])


def _default_plan_steps_for_intent(intent: str) -> list[dict[str, Any]]:
    """Return deterministic fallback plan steps by intent."""

    product_ad_plans: dict[str, list[dict[str, Any]]] = {
        "product_ad_strategy": [
            {"step_id": 1, "name": "识别商户与商品实体", "tool": "entity_parser"},
            {"step_id": 2, "name": "挖掘高价值主推品", "tool": "mine_high_value_products"},
            {"step_id": 3, "name": "融合商品增长分与召回线索", "tool": "rank_ad_candidates"},
            {"step_id": 4, "name": "检索商品级广告策略知识", "tool": "search_business_knowledge"},
            {"step_id": 5, "name": "生成商品级广告策略报告", "tool": "report_generator"},
        ],
        "sku_mining": [
            {"step_id": 1, "name": "识别商户实体", "tool": "entity_parser"},
            {"step_id": 2, "name": "计算 Product Growth Score", "tool": "mine_high_value_products"},
            {"step_id": 3, "name": "检索主推品筛选知识", "tool": "search_business_knowledge"},
            {"step_id": 4, "name": "生成主推品候选排序", "tool": "report_generator"},
        ],
        "bid_recommendation": [
            {"step_id": 1, "name": "识别商品与目标 ROI", "tool": "entity_parser"},
            {"step_id": 2, "name": "计算 ROI 约束下的出价区间", "tool": "recommend_bid_range"},
            {"step_id": 3, "name": "模拟不同加价幅度效果", "tool": "simulate_bid_strategy"},
            {"step_id": 4, "name": "检索 ROI 守护知识", "tool": "search_business_knowledge"},
            {"step_id": 5, "name": "生成出价建议报告", "tool": "report_generator"},
        ],
        "sku_recall": [
            {"step_id": 1, "name": "识别搜索 Query", "tool": "query_parser"},
            {"step_id": 2, "name": "执行 Query-SKU 多路召回", "tool": "recall_query_to_sku"},
            {"step_id": 3, "name": "融合召回分与商品增长分排序", "tool": "rank_ad_candidates"},
            {"step_id": 4, "name": "检索召回策略知识", "tool": "search_business_knowledge"},
            {"step_id": 5, "name": "生成召回解释报告", "tool": "report_generator"},
        ],
        "poi_vs_product_ad_comparison": [
            {"step_id": 1, "name": "识别商户实体", "tool": "entity_parser"},
            {
                "step_id": 2,
                "name": "对比 POI 级与商品级广告表现",
                "tool": "compare_poi_vs_product_ads",
            },
            {
                "step_id": 3,
                "name": "检索商品级广告适用场景知识",
                "tool": "search_business_knowledge",
            },
            {"step_id": 4, "name": "生成对比分析报告", "tool": "report_generator"},
        ],
    }
    if intent in product_ad_plans:
        return product_ad_plans[intent]
    return [
        {"step_id": 1, "name": "计算指标变化", "tool": "compare_periods"},
        {"step_id": 2, "name": "检索业务知识", "tool": "search_business_knowledge"},
        {"step_id": 3, "name": "生成诊断报告", "tool": "diagnosis_generator"},
    ]


def _infer_intent_from_query(query: str, entity_id: str) -> tuple[str, str, list[str]]:
    """Apply lightweight rules when mock LLM output is incomplete."""

    normalized_query = query.upper()
    ad_intent, ad_metric, ad_tools = _infer_product_ad_intent_from_query(query)
    if ad_intent != "unknown":
        return ad_intent, ad_metric, ad_tools

    business_terms = ("经营表现", "经营分析", "经营异常", "活动", "价格竞争力")
    traffic_terms = ("点击率", "转化率")
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
    if "差评" in query or "评价" in query:
        return (
            "review_analysis",
            "review",
            ["analyze_review_topics", "search_business_knowledge"],
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


def _needs_review_analysis(state: AgentState, query: str) -> bool:
    """Return whether Review Tool evidence is useful for this query."""

    return state.intent in {
        "business_diagnosis",
        "refund_analysis",
        "review_analysis",
    } or any(term in query for term in ("差评", "评价", "物流", "续航", "佩戴"))


def _needs_campaign_analysis(state: AgentState, query: str) -> bool:
    """Return whether Campaign Tool evidence is useful for this query."""

    return state.intent in {"business_diagnosis", "traffic_analysis"} or any(
        term in query for term in ("活动", "价格竞争力", "主会场", "券", "满减")
    )


def _run_review_tools(
    state: AgentState,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> None:
    """Run review analysis and period comparison with compatibility keys."""

    review_analysis = analyze_review_topics(state.entity_id, current_start, current_end)
    review_period_comparison = compare_review_periods(
        state.entity_id,
        current_start,
        current_end,
        baseline_start,
        baseline_end,
    )
    state.tool_results["review_analysis"] = review_analysis
    state.tool_results["review_period_comparison"] = review_period_comparison
    state.tool_results["review_topic_analysis"] = review_analysis


def _run_campaign_tools(
    state: AgentState,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> None:
    """Run campaign analysis and period comparison with compatibility keys."""

    campaign_participation = check_campaign_participation(
        state.entity_id,
        current_start,
        current_end,
    )
    campaign_context_comparison = compare_campaign_context(
        state.entity_id,
        current_start,
        current_end,
        baseline_start,
        baseline_end,
    )
    state.tool_results["campaign_participation"] = campaign_participation
    state.tool_results["campaign_context_comparison"] = campaign_context_comparison
    state.tool_results["campaign_analysis"] = campaign_participation


def _resolve_time_range(state: AgentState) -> dict[str, Any]:
    """Return a complete current/baseline time range."""

    return {**DEFAULT_TIME_RANGE, **state.time_range}


def _needs_core_metrics(state: AgentState) -> bool:
    """Return whether the core Metrics Tool group should run."""

    if state.intent in {
        "business_diagnosis",
        "refund_analysis",
        "traffic_analysis",
        "review_analysis",
    }:
        return True
    query = _effective_query(state)
    return state.entity_type == "product" and state.intent in PRODUCT_AD_INTENTS and any(
        term in query.upper() or term in query
        for term in ("GMV", "退款率", "点击率", "转化率", "CTR", "CVR")
    )


def _run_core_metric_tools(
    state: AgentState,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> None:
    """Run deterministic core metric tools and compatibility aliases."""

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

    if state.intent in {"business_diagnosis", "traffic_analysis"}:
        gmv_decomposition = decompose_gmv_change(
            state.entity_id,
            current_start,
            current_end,
            baseline_start,
            baseline_end,
        )
        state.tool_results["gmv_decomposition"] = gmv_decomposition
        state.tool_results["gmv_contribution"] = gmv_decomposition


def _run_peer_period_comparisons(
    state: AgentState,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> None:
    """Run period comparisons for explicitly mentioned peer products."""

    if not state.related_entity_ids:
        return
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


def _build_rag_query_terms(state: AgentState) -> list[str]:
    """Build retrieval terms from query, intent, metric, and tool signals."""

    retrieval_terms = [_effective_query(state), state.intent, state.metric]
    if state.intent in {"product_ad_strategy", "sku_mining"}:
        retrieval_terms.append("商品级广告 主推品 爆品 CVR GMV占比 PCVR ROI 履约风险")
    elif state.intent == "bid_recommendation":
        retrieval_terms.append("PCVR 售价 历史ROI CPC 出价区间 智能调价 ROI守护")
    elif state.intent == "sku_recall":
        retrieval_terms.append("Query SKU 关键词倒排 Query扩展 向量匹配 召回 排序")
    elif state.intent == "poi_vs_product_ad_comparison":
        retrieval_terms.append("POI级广告 商品级广告 高意向搜索 匹配效率 CTR CVR ROI")

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

    review_analysis = state.tool_results.get(
        "review_analysis",
        state.tool_results.get("review_topic_analysis", {}),
    )
    top_topics = review_analysis.get("top_topics", [])
    if "续航不达预期" in top_topics:
        retrieval_terms.append("续航 描述不符 评价分析 售后")
    if "物流慢" in top_topics:
        retrieval_terms.append("物流慢 售后 退款 差评")

    campaign_participation = state.tool_results.get(
        "campaign_participation",
        state.tool_results.get("campaign_analysis", {}),
    )
    if campaign_participation.get("risk_level") == "high":
        retrieval_terms.append("活动参与不足 价格竞争力 满减 类目活动")
    return retrieval_terms


def _record_rag_security(state: AgentState) -> None:
    """Record RAG prompt-injection cleanup warnings when risky chunks appear."""

    risky_docs = [
        doc
        for doc in state.retrieved_docs
        if doc.get("security_risk_level") in {"medium", "high"}
    ]
    if not risky_docs:
        return

    risk_level = (
        "high"
        if any(doc.get("security_risk_level") == "high" for doc in risky_docs)
        else "medium"
    )
    matched_patterns = sorted(
        {
            pattern
            for doc in risky_docs
            for pattern in doc.get("injection_patterns", [])
        }
    )
    rag_security = {
        "risk_level": risk_level,
        "risky_doc_count": len(risky_docs),
        "matched_patterns": matched_patterns,
        "action": "sanitized_untrusted_context",
        "warning": "部分检索内容存在潜在 Prompt Injection 风险，已做清洗处理。",
    }
    state.tool_results["rag_security"] = rag_security
    security_result = dict(state.tool_results.get("security", {}))
    security_result["rag_security"] = rag_security
    security_result["risk_level"] = risk_level
    state.tool_results["security"] = security_result


def prompt_guard_node(state: AgentState) -> AgentState:
    """Detect prompt injection and expose a sanitized query to downstream nodes."""

    try:
        result = PromptInjectionGuard().analyze(state.user_query)
        state.safe_user_query = result.sanitized_query
        state.security_flags = result.as_dict()
        state.tool_results["prompt_guard"] = result.as_dict()
        state.tool_results["security"] = {
            "prompt_injection": result.as_dict(),
            "risk_level": result.risk_level,
        }
    except Exception as error:
        _append_error(state, "prompt_guard_node", error)
        state.safe_user_query = state.user_query

    return state


def intent_router_node(state: AgentState) -> AgentState:
    """Recognize intent, entity, metric, time range, and required tools."""

    try:
        llm = LLMService()
        query = _effective_query(state)
        prompt = INTENT_ROUTER_PROMPT.format(query=query)
        result = llm.generate_json(prompt)
        _record_llm_provider(state, llm)

        merchant_id = _extract_merchant_id_from_query(query)
        product_id = _extract_product_id_from_query(query)
        entity_id = result.get("entity_id") or product_id or merchant_id
        if not entity_id:
            entity_id = product_id or merchant_id

        intent = result.get("intent", "")
        metric = result.get("metric", "")
        need_tools = result.get("need_tools", [])
        ad_intent, ad_metric, ad_tools = _infer_product_ad_intent_from_query(query)
        if ad_intent != "unknown":
            intent, metric, need_tools = ad_intent, ad_metric, ad_tools
        elif intent in {"", "unknown"} or metric in {"", "unknown"}:
            intent, metric, need_tools = _infer_intent_from_query(query, entity_id)

        state.intent = intent
        if product_id:
            state.entity_type = "product"
            entity_id = product_id
        elif merchant_id:
            state.entity_type = "merchant"
            entity_id = merchant_id
        else:
            state.entity_type = result.get("entity_type", "unknown")
        state.entity_id = entity_id
        state.domain = (
            "local_commerce_product_ad"
            if intent in PRODUCT_AD_INTENTS
            else "business_diagnosis"
        )
        state.route_type = "product_ad_tool" if intent in PRODUCT_AD_INTENTS else "metrics_rag"
        state.related_entity_ids = [
            product_id
            for product_id in _extract_product_ids_from_query(query)
            if product_id != entity_id
        ]
        state.metric = metric
        state.time_range = result.get("time_range") or DEFAULT_TIME_RANGE.copy()
        state.tool_results["intent_router"] = {
            "need_tools": need_tools,
            "raw_result": result,
        }
        security = SecurityService()
        state.tool_results["tool_policy"] = {
            "validated_tools": [
                {
                    "tool": tool_name,
                    **security.validate_tool_name(str(tool_name)),
                }
                for tool_name in need_tools
            ],
            "policy": "allowlist",
        }
    except Exception as error:
        _append_error(state, "intent_router_node", error)

    return state


def planner_node(state: AgentState) -> AgentState:
    """Generate executable plan steps from intent and user query."""

    try:
        llm = LLMService()
        prompt = PLANNER_PROMPT.format(query=_effective_query(state), intent=state.intent)
        result = llm.generate_json(prompt)
        _record_llm_provider(state, llm)
        plan_steps = result.get("plan_steps", [])
        if state.intent in PRODUCT_AD_INTENTS or not plan_steps:
            plan_steps = _default_plan_steps_for_intent(state.intent)
        state.plan_steps = plan_steps
    except Exception as error:
        _append_error(state, "planner_node", error)

    return state


def metrics_tool_node(state: AgentState) -> AgentState:
    """Call metric and deterministic business tools for supported intents."""

    if "metrics" in state.disabled_components:
        disabled_result = {
            "disabled": True,
            "reason": "metrics component disabled for ablation.",
        }
        state.tool_results["metrics_ablation"] = disabled_result
        state.tool_results["metrics_disabled"] = True
        return state

    query = _effective_query(state)
    needs_metrics = _needs_core_metrics(state)
    needs_review = _needs_review_analysis(state, query)
    needs_campaign = _needs_campaign_analysis(state, query)
    if not any([needs_metrics, needs_review, needs_campaign]):
        return state

    if not state.entity_id:
        state.errors.append({"node": "metrics_tool_node", "error": "Missing product entity_id."})
        return state

    try:
        time_range = _resolve_time_range(state)
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

        if needs_metrics:
            _run_core_metric_tools(
                state,
                current_start,
                current_end,
                baseline_start,
                baseline_end,
            )
            _run_peer_period_comparisons(
                state,
                current_start,
                current_end,
                baseline_start,
                baseline_end,
            )

        if needs_review and "review" not in state.disabled_components:
            _run_review_tools(
                state,
                current_start,
                current_end,
                baseline_start,
                baseline_end,
            )
        if needs_campaign and "campaign" not in state.disabled_components:
            _run_campaign_tools(
                state,
                current_start,
                current_end,
                baseline_start,
                baseline_end,
            )
    except Exception as error:
        _append_error(state, "metrics_tool_node", error)

    return state


def _resolve_merchant_from_product(product_id: str) -> str:
    """Find merchant_id for a local-ad product."""

    if not product_id:
        return ""
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT merchant_id
                FROM local_ad_sku_candidates
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchone()
    except Exception:
        return ""
    return str(row["merchant_id"]) if row else ""


def _resolve_product_ad_entities(state: AgentState) -> dict[str, Any]:
    """Extract entities used by product-level ad tools."""

    query = _effective_query(state)
    product_id = _extract_product_id_from_query(query)
    merchant_id = _extract_merchant_id_from_query(query)
    if state.entity_type == "product" and state.entity_id:
        product_id = state.entity_id
    if state.entity_type == "merchant" and state.entity_id:
        merchant_id = state.entity_id
    if product_id and not merchant_id:
        merchant_id = _resolve_merchant_from_product(product_id)
    return {
        "product_id": product_id,
        "merchant_id": merchant_id,
        "recall_query": _extract_recall_query_from_user_query(query),
        "target_roi": _extract_target_roi_from_query(query),
        "bid_multiplier": _extract_bid_multiplier_from_query(query),
    }


def product_ad_tool_node(state: AgentState) -> AgentState:
    """Run product-level advertising tools for local commerce intents."""

    if "product_ad" in state.disabled_components:
        disabled_result = {
            "disabled": True,
            "reason": "product_ad component disabled for ablation.",
        }
        state.ad_results = disabled_result
        state.tool_results["product_ad"] = disabled_result
        return state

    if state.intent not in PRODUCT_AD_INTENTS:
        return state

    try:
        entities = _resolve_product_ad_entities(state)
        product_id = entities["product_id"]
        merchant_id = entities["merchant_id"]
        recall_query = entities["recall_query"]
        target_roi = entities["target_roi"]
        bid_multiplier = entities["bid_multiplier"]
        result: dict[str, Any] = {
            "intent": state.intent,
            "entities": entities,
        }

        if state.intent == "product_ad_strategy":
            if not merchant_id and not product_id:
                merchant_id = "M001"
                result["default_merchant_used"] = True
            if merchant_id:
                result["sku_mining"] = mine_high_value_products(merchant_id)
                result["ranked_candidates"] = rank_ad_candidates(merchant_id=merchant_id)
            elif product_id:
                result["bid_range_reference"] = recommend_bid_range(product_id, target_roi)
                result["ranked_candidates"] = rank_ad_candidates(
                    merchant_id=_resolve_merchant_from_product(product_id)
                )
            else:
                result["error"] = {
                    "code": "missing_merchant_or_product",
                    "message": "需要补充 merchant_id 或 product_id 才能生成主推品建议。",
                }
        elif state.intent == "sku_mining":
            if merchant_id:
                result["sku_mining"] = mine_high_value_products(merchant_id)
                result["ranked_candidates"] = rank_ad_candidates(merchant_id=merchant_id)
            else:
                result["error"] = {
                    "code": "missing_merchant_id",
                    "message": "需要补充 merchant_id 才能挖掘主推品。",
                }
        elif state.intent == "sku_recall":
            result["query_recall"] = recall_query_to_sku(recall_query)
            result["ranked_candidates"] = rank_ad_candidates(
                query=recall_query,
                merchant_id=merchant_id or None,
            )
        elif state.intent == "bid_recommendation":
            if product_id:
                result["bid_range"] = recommend_bid_range(product_id, target_roi)
                result["bid_simulation"] = simulate_bid_strategy(product_id, bid_multiplier)
            else:
                result["error"] = {
                    "code": "missing_product_id",
                    "message": "需要补充 product_id 才能计算出价区间。",
                }
        elif state.intent == "poi_vs_product_ad_comparison":
            resolved_merchant_id = merchant_id or "M001"
            result["comparison"] = compare_poi_vs_product_ads(resolved_merchant_id)
            result["default_merchant_used"] = not bool(merchant_id)

        state.ad_results = result
        state.tool_results["product_ad"] = result
    except Exception as error:
        _append_error(state, "product_ad_tool_node", error)
        state.ad_results = {
            "ok": False,
            "error": {"code": "tool_node_error", "message": str(error)},
        }
        state.tool_results["product_ad"] = state.ad_results

    return state


def recommendation_scorer_node(state: AgentState) -> AgentState:
    """Build a compact recommendation layer from metrics, ad tools, and RAG."""

    try:
        if state.intent in {"business_diagnosis", "refund_analysis", "traffic_analysis"}:
            comparison = state.tool_results.get("period_comparison", {})
            root_causes = []
            for metric_name in ("gmv", "ctr", "cvr", "refund_rate"):
                change = _metric_change(comparison, metric_name)
                if change.get("absolute_change") in {None, 0}:
                    continue
                confidence = "medium"
                if metric_name == "refund_rate" and change.get("absolute_change", 0) > 0:
                    confidence = "high"
                if metric_name != "refund_rate" and change.get("absolute_change", 0) < 0:
                    confidence = "high"
                root_causes.append(
                    {
                        "root_cause": metric_name,
                        "metric_support": change,
                        "rag_support": [doc.get("source") for doc in state.retrieved_docs[:3]],
                        "confidence": confidence,
                        "uncertainty": "指标为近似归因，需要结合运营动作和实验继续验证",
                    }
                )
            state.recommendation_result = {"root_causes": root_causes}
        elif state.intent in {"product_ad_strategy", "sku_mining"}:
            product_ad = state.ad_results or state.tool_results.get("product_ad", {})
            mining = product_ad.get("sku_mining", {})
            ranked = product_ad.get("ranked_candidates", {})
            state.recommendation_result = {
                "recommended_products": mining.get("candidates", []),
                "ranked_candidates": ranked.get("ranked_candidates", []),
            }
        elif state.intent == "bid_recommendation":
            product_ad = state.ad_results or state.tool_results.get("product_ad", {})
            state.recommendation_result = {
                "bid_recommendation": product_ad.get("bid_range", {}),
                "bid_simulation": product_ad.get("bid_simulation", {}),
            }
        elif state.intent == "sku_recall":
            product_ad = state.ad_results or state.tool_results.get("product_ad", {})
            recall = product_ad.get("query_recall", {})
            ranked = product_ad.get("ranked_candidates", {})
            state.recommendation_result = {
                "recalled_products": recall.get("results", []),
                "ranked_candidates": ranked.get("ranked_candidates", []),
                "recall_paths_used": recall.get("recall_paths_used", []),
            }
        elif state.intent == "poi_vs_product_ad_comparison":
            product_ad = state.ad_results or state.tool_results.get("product_ad", {})
            comparison = product_ad.get("comparison", {})
            state.recommendation_result = {
                "comparison": comparison.get("comparison", []),
                "insights": comparison.get("insights", []),
            }

        state.evidence_alignment = {
            "tool_result_keys": sorted(state.tool_results.keys()),
            "retrieved_doc_sources": [doc.get("source") for doc in state.retrieved_docs],
            "claim_policy": (
                "major conclusions should be supported by metrics, product_ad_tool, or RAG"
            ),
        }
        state.tool_results["recommendation_result"] = state.recommendation_result
        state.tool_results["evidence_alignment"] = state.evidence_alignment
    except Exception as error:
        _append_error(state, "recommendation_scorer_node", error)

    return state


def review_tool_node(state: AgentState) -> AgentState:
    """Analyze review topics when the query or intent needs customer feedback evidence."""

    if "review" in state.disabled_components:
        state.tool_results["review_ablation"] = {
            "disabled": True,
            "reason": "review component disabled for ablation.",
        }
        return state

    query = _effective_query(state)
    needs_review = _needs_review_analysis(state, query)
    if not needs_review:
        return state
    if "review_analysis" in state.tool_results:
        return state

    if not state.entity_id:
        state.errors.append({"node": "review_tool_node", "error": "Missing product entity_id."})
        return state

    try:
        time_range = _resolve_time_range(state)
        _run_review_tools(
            state,
            time_range["current_start"],
            time_range["current_end"],
            time_range["baseline_start"],
            time_range["baseline_end"],
        )
    except Exception as error:
        _append_error(state, "review_tool_node", error)

    return state


def campaign_tool_node(state: AgentState) -> AgentState:
    """Analyze campaign eligibility and participation when relevant."""

    if "campaign" in state.disabled_components:
        state.tool_results["campaign_ablation"] = {
            "disabled": True,
            "reason": "campaign component disabled for ablation.",
        }
        return state

    query = _effective_query(state)
    needs_campaign = _needs_campaign_analysis(state, query)
    if not needs_campaign:
        return state
    if "campaign_participation" in state.tool_results:
        return state

    if not state.entity_id:
        state.errors.append({"node": "campaign_tool_node", "error": "Missing product entity_id."})
        return state

    try:
        time_range = _resolve_time_range(state)
        _run_campaign_tools(
            state,
            time_range["current_start"],
            time_range["current_end"],
            time_range["baseline_start"],
            time_range["baseline_end"],
        )
    except Exception as error:
        _append_error(state, "campaign_tool_node", error)

    return state


def rag_retriever_node(state: AgentState) -> AgentState:
    """Retrieve knowledge evidence based on query and metric signals."""

    if "rag" in state.disabled_components:
        state.retrieved_docs = []
        disabled_result = {
            "disabled": True,
            "reason": "RAG component disabled for ablation.",
        }
        state.tool_results["rag_ablation"] = disabled_result
        state.tool_results["rag_search"] = {
            "query": _effective_query(state),
            "evidence_summary": "RAG disabled for ablation.",
            **disabled_result,
        }
        return state

    fallback = FallbackService()
    try:
        query = " ".join(_build_rag_query_terms(state))
        result = fallback.normalize_rag_result(search_business_knowledge(query), query)
        state.retrieved_docs = result["results"]
        state.tool_results["rag_search"] = {
            "query": result["query"],
            "evidence_summary": result["evidence_summary"],
            "security_summary": result.get("security_summary", {}),
        }
        _record_rag_security(state)
    except Exception as error:
        _append_error(state, "rag_retriever_node", error)
        fallback_result = fallback.normalize_rag_result(None, _effective_query(state))
        state.retrieved_docs = fallback_result["results"]
        state.tool_results["rag_search"] = {
            "query": fallback_result["query"],
            "evidence_summary": fallback_result["evidence_summary"],
        }

    return state


def diagnosis_generator_node(state: AgentState) -> AgentState:
    """Generate a structured business diagnosis report."""

    try:
        report_service = ReportService()
        state.diagnosis = report_service.generate_diagnosis(state)
        _record_llm_provider(state, report_service.llm)
    except Exception as error:
        _append_error(state, "diagnosis_generator_node", error)
        state.diagnosis = FallbackService().generate_diagnosis_report(state)

    return state


def reflection_checker_node(state: AgentState) -> AgentState:
    """Check whether the diagnosis is structurally complete and evidence-backed."""

    if "reflection" in state.disabled_components:
        state.reflection_result = {
            "pass": True,
            "disabled": True,
            "overall_confidence": "disabled",
            "issues": [],
            "suggestions": ["Reflection Checker disabled for ablation."],
        }
        state.tool_results["reflection_ablation"] = {
            "disabled": True,
            "reason": "reflection component disabled for ablation.",
        }
        return state

    state.reflection_result = EvidenceChecker().run(
        state.diagnosis or "",
        state.tool_results,
        state.retrieved_docs,
    )
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
    reflection_passed = state.reflection_result.get("pass")
    confidence = state.reflection_result.get("overall_confidence", "unknown")
    issue_summary = "；".join(state.reflection_result.get("issues", [])[:3])
    reflection_text = (
        f"{'通过' if reflection_passed else '未通过'}；"
        f"overall_confidence={confidence}"
        f"{'；issue 摘要：' + issue_summary if issue_summary else ''}"
    )

    state.final_answer = (
        f"{state.diagnosis}\n\n"
        f"---\n"
        f"trace_id: {state.trace_id}\n"
        f"执行步骤摘要：\n{step_summary}\n"
        f"反思校验：{reflection_text}"
    )
    state.final_answer = SecurityService().filter_sensitive_output(state.final_answer)
    return state
