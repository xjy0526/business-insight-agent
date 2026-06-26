"""Diagnosis report generation service for BusinessInsight Agent."""

from __future__ import annotations

import json
from typing import Any

from app.agent.prompts import DIAGNOSIS_PROMPT
from app.agent.state import AgentState
from app.services.fallback_service import FallbackService
from app.services.llm_service import LLMService
from app.tools.product_ad_tool import PRODUCT_AD_INTENTS


def _metric_change(
    comparison: dict[str, Any],
    metric_name: str,
) -> dict[str, Any]:
    """Return one metric change record from compare_periods output."""

    return comparison.get("changes", {}).get(
        metric_name,
        {"current": 0, "baseline": 0, "absolute_change": 0, "percent_change": None},
    )


def _format_percent(value: float | None) -> str:
    """Format a ratio as a percentage string."""

    if value is None:
        return "无法计算"
    return f"{value * 100:.2f}%"


def _format_percent_change(value: float | None) -> str:
    """Format a relative change ratio."""

    if value is None:
        return "基准期为 0，无法计算变化率"
    return f"{value * 100:+.2f}%"


def _find_channel(channels: list[dict[str, Any]], channel_name: str) -> dict[str, Any]:
    """Find one channel row by name."""

    return next((channel for channel in channels if channel["channel"] == channel_name), {})


class ReportService:
    """Generate deterministic or LLM-backed structured diagnosis reports."""

    def __init__(
        self,
        llm: LLMService | None = None,
        fallback: FallbackService | None = None,
    ) -> None:
        self.llm = llm or LLMService()
        self.fallback = fallback or FallbackService()

    def generate_diagnosis(self, state: AgentState) -> str:
        """Generate a structured diagnosis report with local fallback support."""

        if any(error.get("node") == "metrics_tool_node" for error in state.errors):
            report = self.fallback.generate_diagnosis_report(state)
            self.llm.record_local_generation(state.user_query, report, status="fallback_report")
            return report
        if state.tool_results.get("metrics_disabled"):
            report = self.fallback.generate_diagnosis_report(state)
            self.llm.record_local_generation(state.user_query, report, status="fallback_report")
            return report

        if state.intent in PRODUCT_AD_INTENTS and state.ad_results:
            report = self.build_product_ad_report(state)
            self.llm.record_local_generation(state.user_query, report, status="mock_template")
            return report

        if state.intent == "unknown" and not state.entity_id:
            report = self._build_unknown_report(state)
            self.llm.record_local_generation(state.user_query, report, status="mock_template")
            return report

        if not self.llm.uses_mock:
            report = self.llm.generate(
                DIAGNOSIS_PROMPT.format(
                    query=state.safe_user_query or state.user_query,
                    metrics_result=json.dumps(
                        state.tool_results,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    rag_evidence=json.dumps(
                        self._safe_retrieved_docs(state.retrieved_docs),
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            )
            if report.strip():
                return report
            fallback_report = self.fallback.generate_diagnosis_report(state)
            self.llm.record_local_generation(
                state.user_query,
                fallback_report,
                status="fallback_report",
            )
            return fallback_report

        report = self.build_mock_diagnosis_report(state)
        self.llm.record_local_generation(state.user_query, report, status="mock_template")
        return report

    def build_mock_diagnosis_report(self, state: AgentState) -> str:
        """Build a deterministic but business-like Chinese diagnosis report."""

        product = state.tool_results.get("product_basic_info", {})
        comparison = state.tool_results.get("period_comparison", {})
        current_gmv = state.tool_results.get("current_gmv", {})
        baseline_gmv = state.tool_results.get("baseline_gmv", {})
        current_refund = state.tool_results.get("current_refund", {})
        baseline_refund = state.tool_results.get("baseline_refund", {})
        review_analysis = state.tool_results.get(
            "review_analysis",
            state.tool_results.get("review_topic_analysis", {}),
        )
        review_period_comparison = state.tool_results.get("review_period_comparison", {})
        campaign_analysis = state.tool_results.get(
            "campaign_participation",
            state.tool_results.get("campaign_analysis", {}),
        )
        campaign_context_comparison = state.tool_results.get("campaign_context_comparison", {})
        gmv_contribution = state.tool_results.get(
            "gmv_decomposition",
            state.tool_results.get("gmv_contribution", {}),
        )
        current_channels = state.tool_results.get("current_channel_breakdown", {}).get(
            "channels",
            [],
        )
        baseline_channels = state.tool_results.get("baseline_channel_breakdown", {}).get(
            "channels",
            [],
        )
        current_search = _find_channel(current_channels, "search")
        baseline_search = _find_channel(baseline_channels, "search")

        gmv_change = _metric_change(comparison, "gmv")
        ctr_change = _metric_change(comparison, "ctr")
        cvr_change = _metric_change(comparison, "cvr")
        aov_change = _metric_change(comparison, "aov")
        refund_change = _metric_change(comparison, "refund_rate")

        product_label = product.get("product_name") or state.entity_id or "目标商品"
        evidence_sources = self._collect_evidence_sources(state.retrieved_docs)
        evidence_source_text = (
            ", ".join(evidence_sources) if evidence_sources else "未检索到足够知识证据"
        )
        rag_security_note = self._build_rag_security_note(state)
        query = state.safe_user_query or state.user_query
        peer_summary = self._build_peer_summary(state)
        uncertainty_note = self._build_uncertainty_note(query)
        contribution_text = self._build_contribution_summary(gmv_contribution)
        primary_contribution_text = self._build_primary_contribution_text(gmv_contribution)
        review_text = self._build_review_summary(review_analysis, review_period_comparison)
        campaign_text = self._build_campaign_summary(
            campaign_analysis,
            campaign_context_comparison,
        )
        review_attribution_text = self._build_review_attribution_text(review_analysis)
        campaign_attribution_text = self._build_campaign_attribution_text(campaign_analysis)

        return (
            f"## 问题概述\n"
            f"用户问题关注“{query}”。"
            f"当前识别对象为 {state.entity_id}（{product_label}），"
            f"分析口径为 2026-04-01 至 2026-04-30，对比基准期 2026-03-01 至 2026-03-31。"
            f"从工具计算看，4 月 GMV 为 {current_gmv.get('gmv', 0):.2f}，"
            f"低于 3 月的 {baseline_gmv.get('gmv', 0):.2f}，"
            f"需要按流量、转化、客单价和售后共同归因。"
            f"{peer_summary}{uncertainty_note}\n\n"
            f"## 指标拆解\n"
            f"- GMV：当前 {gmv_change.get('current', 0):.2f}，"
            f"基准 {gmv_change.get('baseline', 0):.2f}，"
            f"变化 {gmv_change.get('absolute_change', 0):.2f}，"
            f"变化率 {_format_percent_change(gmv_change.get('percent_change'))}。\n"
            f"- 点击率 CTR：当前 {_format_percent(ctr_change.get('current'))}，"
            f"基准 {_format_percent(ctr_change.get('baseline'))}，"
            f"变化 {_format_percent_change(ctr_change.get('percent_change'))}。"
            f"其中 search 渠道点击率从 {_format_percent(baseline_search.get('ctr'))} "
            f"降至 {_format_percent(current_search.get('ctr'))}。\n"
            f"- 转化率 CVR：当前 {_format_percent(cvr_change.get('current'))}，"
            f"基准 {_format_percent(cvr_change.get('baseline'))}，"
            f"变化 {_format_percent_change(cvr_change.get('percent_change'))}。\n"
            f"- 客单价 AOV：当前 {aov_change.get('current', 0):.2f}，"
            f"基准 {aov_change.get('baseline', 0):.2f}，"
            f"变化 {_format_percent_change(aov_change.get('percent_change'))}。\n"
            f"- 退款率：当前 {_format_percent(current_refund.get('refund_rate'))}，基准 "
            f"{_format_percent(baseline_refund.get('refund_rate'))}，变化 "
            f"{_format_percent_change(refund_change.get('percent_change'))}。\n\n"
            f"{contribution_text}"
            f"{review_text}"
            f"{campaign_text}"
            f"## 主要归因\n"
            f"1. {primary_contribution_text}"
            f"2. {review_attribution_text}"
            f"3. {campaign_attribution_text}\n"
            f"## 证据来源\n"
            f"- 指标工具：compare_periods、calculate_gmv、calculate_refund_rate、"
            f"analyze_channel_breakdown、decompose_gmv_change。\n"
            f"- Review Tool：analyze_review_topics、compare_review_periods。\n"
            f"- Campaign Tool：check_campaign_participation、compare_campaign_context。\n"
            f"- RAG 文档：{evidence_source_text}。{rag_security_note}\n\n"
            f"## 优化建议\n"
            f"1. 优先复盘 P1001 的 4 月活动参与状态，争取进入音频类目主会场"
            f"或提高券曝光，修复价格竞争力。\n"
            f"2. 针对 search 点击率下降，重做主图利益点、标题关键词和到手价展示，"
            f"并和竞品搜索卡片对比。\n"
            f"3. 针对退款率升高，排查物流时效、续航描述、佩戴舒适度和批次质量，"
            f"必要时调整详情页承诺并推动供应链复检。\n"
            f"4. 持续监控 GMV、点击率、转化率、退款率和差评主题，按周验证优化动作是否有效。"
            f"{self._build_business_course_addendum(state)}"
        )

    def build_product_ad_report(self, state: AgentState) -> str:
        """Build deterministic product-level advertising reports."""

        if state.intent in {"product_ad_strategy", "sku_mining"}:
            return self._build_sku_mining_report(state)
        if state.intent == "bid_recommendation":
            return self._build_bid_recommendation_report(state)
        if state.intent == "sku_recall":
            return self._build_sku_recall_report(state)
        if state.intent == "poi_vs_product_ad_comparison":
            return self._build_poi_vs_product_report(state)
        return self.fallback.generate_diagnosis_report(state)

    def _build_unknown_report(self, state: AgentState) -> str:
        """Render a safe clarification-oriented report for vague queries."""

        return (
            f"## 问题概述\n用户问题“{state.safe_user_query or state.user_query}”问题不明确。"
            "当前缺少可执行分析所需的商户ID、商品ID或具体问题类型。\n\n"
            "## 需要补充\n"
            "- 商户ID，例如 M001。\n"
            "- 商品ID，例如 P1001。\n"
            "- 具体目标，例如 GMV 下滑归因、退款率分析、主推品挖掘、"
            "Query-SKU 召回或 ROI 出价守护。\n\n"
            "## 证据来源\n"
            "未调用确定性指标或商品广告工具，因此不输出强结论。\n\n"
            "## 优化建议\n"
            "请补充商户ID、商品ID和要分析的问题，Agent 再生成可追溯的工具结果与报告。"
        )

    def _build_sku_mining_report(self, state: AgentState) -> str:
        """Render product-level ad strategy and SKU mining report."""

        product_ad = state.ad_results or state.tool_results.get("product_ad", {})
        mining = product_ad.get("sku_mining", {})
        ranked = product_ad.get("ranked_candidates", {})
        candidates = mining.get("candidates") or ranked.get("ranked_candidates", [])
        if product_ad.get("error"):
            error_message = product_ad["error"].get("message", "需要补充商户或商品信息。")
            return (
                f"## 问题概述\n用户问题关注“{state.safe_user_query or state.user_query}”。"
                f"{error_message}\n\n"
                "## 风险与待验证\n当前为 synthetic demo，缺少 merchant_id 或 product_id 时"
                "不能输出确定主推品排序。"
            )

        candidate_lines = "\n".join(
            (
                f"- rank {candidate.get('rank')}: {candidate.get('product_id')} "
                f"{candidate.get('product_name')}，product_growth_score="
                f"{candidate.get('product_growth_score', candidate.get('final_score'))}，"
                f"CVR {_format_percent(candidate.get('cvr'))}，GMV占比 "
                f"{_format_percent(candidate.get('gmv_share'))}，PCVR "
                f"{_format_percent(candidate.get('pcvr'))}，历史ROI "
                f"{candidate.get('historical_roi', '-')}，评分 "
                f"{candidate.get('rating', '-')}，退款率 "
                f"{_format_percent(candidate.get('refund_rate'))}，risk_flags="
                f"{'、'.join(candidate.get('risk_flags', [])) or '暂无明显风险'}。"
            )
            for candidate in candidates[:5]
        )
        reason_items = []
        for candidate in candidates[:3]:
            reason = "、".join(candidate.get("key_reasons", [])) or candidate.get(
                "recommendation",
                "",
            )
            reason_items.append(f"- {candidate.get('product_id')} 推荐理由：{reason}。")
        reason_lines = "\n".join(reason_items)
        top_candidate = candidates[0] if candidates else {}
        evidence_source_text = self._format_evidence_sources(state)
        return (
            f"## 问题概述\n"
            f"用户问题关注“{state.safe_user_query or state.user_query}”。当前任务是为本地生活商户"
            f"做商品级广告主推品挖掘，并用 CVR、GMV占比、PCVR、历史 ROI、关键词覆盖和"
            f"退款风险约束推荐顺序。\n\n"
            f"## 主推品候选排序\n"
            f"{candidate_lines or '- 暂无可排序候选商品。'}\n\n"
            f"## 推荐理由\n"
            f"{reason_lines or '- 当前缺少足够候选商品，建议补充 merchant_id。'}\n\n"
            f"## 投放建议\n"
            f"- 优先投放商品：{top_candidate.get('product_id', '待确认')} "
            f"{top_candidate.get('product_name', '')}。\n"
            f"- 适合高意向搜索、明确服务项目和团购套餐场景；预算有限时优先看"
            f"GMV占比、CVR、PCVR 与历史 ROI 的综合排序，而不是只看单一指标。\n"
            f"- 若 risk_flags 包含退款率、评分或档期风险，不建议盲目加价，先做小流量 A/B测试。\n\n"
            f"## 证据来源\n"
            f"- product_ad_tool：mine_high_value_products、rank_ad_candidates。\n"
            f"- RAG 文档：{evidence_source_text}。\n\n"
            f"## 风险与待验证\n"
            f"当前为 synthetic demo data。真实投放需结合预算、供给、商户承接能力、"
            f"线上实验和售后质量继续验证。"
        )

    def _build_bid_recommendation_report(self, state: AgentState) -> str:
        """Render bid and ROI guardrail report."""

        product_ad = state.ad_results or state.tool_results.get("product_ad", {})
        bid_range = product_ad.get("bid_range", {})
        simulation = product_ad.get("bid_simulation", {})
        if not bid_range.get("ok"):
            message = bid_range.get("error", product_ad.get("error", {})).get(
                "message",
                "需要补充 product_id 才能计算出价区间。",
            )
            return (
                f"## 问题概述\n用户问题关注“{state.safe_user_query or state.user_query}”。"
                f"{message}\n\n## ROI 守护建议\n缺少商品级 PCVR、price 或 ROI 数据时，"
                "不应给出具体 CPC。"
            )

        cpc_range = bid_range.get("recommended_cpc_range", [])
        evidence_source_text = self._format_evidence_sources(state)
        risk_flags = "、".join(bid_range.get("risk_flags", [])) or "暂无明显风险"
        return (
            f"## 问题概述\n"
            f"用户问题关注“{state.safe_user_query or state.user_query}”。当前任务是估计"
            f"{bid_range.get('product_id')} {bid_range.get('product_name')} 的 CPC 出价区间，"
            f"并检查加价后的 ROI guardrail（ROI守护）。\n\n"
            f"## 出价区间计算\n"
            f"- PCVR：{bid_range.get('pcvr')}；price：{bid_range.get('price')}；"
            f"target_roi：{bid_range.get('target_roi')}。\n"
            f"- expected_revenue_per_click：{bid_range.get('expected_revenue_per_click')}；"
            f"expected_profit_per_click：{bid_range.get('expected_profit_per_click')}。\n"
            f"- max_cpc_by_revenue_roi：{bid_range.get('max_cpc_by_revenue_roi')}；"
            f"max_cpc_by_profit_roi：{bid_range.get('max_cpc_by_profit_roi')}。\n"
            f"- recommended_cpc_range：{cpc_range}；bid_strategy："
            f"{bid_range.get('bid_strategy')}；risk_flags：{risk_flags}。\n\n"
            f"## 加价模拟\n"
            f"- bid_multiplier：{simulation.get('bid_multiplier', '-')}"
            f"（matched_group={simulation.get('matched_group', '-')}）。\n"
            f"- CTR：{_format_percent(simulation.get('ctr'))}；CVR："
            f"{_format_percent(simulation.get('cvr'))}；orders："
            f"{simulation.get('orders', '-')}；ROI：{simulation.get('roi', '-')}；"
            f"roi_status：{simulation.get('roi_status', '-')}。\n\n"
            f"## ROI守护建议\n"
            f"- 如果 ROI 高于目标，可以谨慎加价；如果 ROI 接近目标，需要智能调价保护。\n"
            f"- 如果 ROI 低于目标，不建议继续加价；若退款率偏高，应降低上限出价或先处理履约风险。\n"
            f"- 本次建议使用 {bid_range.get('bid_strategy')} 策略，并通过 A/B测试观察 "
            f"CTR、CVR、订单和 ROI。\n\n"
            f"## 证据来源\n"
            f"- product_ad_tool：recommend_bid_range、simulate_bid_strategy。\n"
            f"- RAG 文档：{evidence_source_text}。"
        )

    def _build_sku_recall_report(self, state: AgentState) -> str:
        """Render Query-SKU recall explanation report."""

        product_ad = state.ad_results or state.tool_results.get("product_ad", {})
        recall = product_ad.get("query_recall", {})
        ranked = product_ad.get("ranked_candidates", {})
        recall_results = recall.get("results", [])
        ranked_candidates = ranked.get("ranked_candidates", [])
        recall_lines = "\n".join(
            (
                f"- {item.get('product_id')} {item.get('product_name')}："
                f"recall_path={item.get('recall_path')}，recall_score="
                f"{item.get('recall_score')}，matched_terms={item.get('matched_terms')}。"
            )
            for item in recall_results[:5]
        )
        ranked_lines = "\n".join(
            (
                f"- rank {item.get('rank')}: {item.get('product_id')} final_score="
                f"{item.get('final_score')}，recall_path={item.get('recall_path')}，"
                f"matched_terms={item.get('matched_terms')}，{item.get('recommendation')}。"
            )
            for item in ranked_candidates[:5]
        )
        evidence_source_text = self._format_evidence_sources(state)
        return (
            f"## 问题概述\n"
            f"用户问题关注“{state.safe_user_query or state.user_query}”。当前任务是解释 Query"
            f" “{recall.get('query', '')}” 应召回哪些 SKU/服务项目。\n\n"
            f"## Query-SKU 召回结果\n"
            f"{recall_lines or '- 暂无召回结果，需要补充更明确 Query。'}\n\n"
            f"## 召回路径解释\n"
            f"- keyword_inverted：词面强匹配，适合 Query 与服务名或套餐词直接重合。\n"
            f"- query_expansion：同义词、服务词或类目扩展，适合相关服务补充召回。\n"
            f"- vector_match：语义相近匹配，适合词面不同但服务意图接近的 Query。\n\n"
            f"## 排序理由\n"
            f"{ranked_lines or '- 暂无融合排序结果。'}\n"
            f"最终排序不仅看 recall_score，还结合 product_growth_score、ROI、"
            f"关键词覆盖和退款风险。\n\n"
            f"## 证据来源\n"
            f"- product_ad_tool：recall_query_to_sku、rank_ad_candidates。\n"
            f"- RAG 文档：{evidence_source_text}。"
        )

    def _build_poi_vs_product_report(self, state: AgentState) -> str:
        """Render POI-level vs product-level ad comparison report."""

        product_ad = state.ad_results or state.tool_results.get("product_ad", {})
        comparison_result = product_ad.get("comparison", {})
        rows = comparison_result.get("comparison", [])
        row_lines = "\n".join(
            (
                f"- {row.get('campaign_type')}：CTR {_format_percent(row.get('ctr'))}，"
                f"CVR {_format_percent(row.get('cvr'))}，orders {row.get('orders')}，"
                f"ROI {row.get('roi')}。"
            )
            for row in rows
        )
        insight_lines = "\n".join(
            f"- {insight}" for insight in comparison_result.get("insights", [])
        )
        evidence_source_text = self._format_evidence_sources(state)
        return (
            f"## 问题概述\n"
            f"用户问题关注“{state.safe_user_query or state.user_query}”。当前对比 POI级广告、"
            f"商品级广告和商品级广告+智能调价的 CTR、CVR、orders 与 ROI。\n\n"
            f"## 指标对比\n"
            f"{row_lines or '- 暂无对比数据。'}\n\n"
            f"## 结论\n"
            f"{insight_lines or '- 商品级广告更适合高意向Query和明确服务需求。'}\n"
            f"- 课程口径结论：商品级广告更适合高意向Query和明确服务需求。\n"
            f"- 商品级广告相比 POI级广告更依赖商品数据治理、供给稳定和 ROI 守护。\n\n"
            f"## 证据来源\n"
            f"- product_ad_tool：compare_poi_vs_product_ads。\n"
            f"- RAG 文档：{evidence_source_text}。"
        )

    def _build_business_course_addendum(self, state: AgentState) -> str:
        """Append course-version attribution and product-ad impact sections."""

        root_causes = state.recommendation_result.get("root_causes", [])
        if not root_causes:
            return ""
        root_lines = "\n".join(
            (
                f"- {item.get('root_cause')}：metric_support={item.get('metric_support')}，"
                f"rag_support={item.get('rag_support')}，confidence={item.get('confidence')}，"
                f"uncertainty={item.get('uncertainty')}。"
            )
            for item in root_causes[:4]
        )
        return (
            f"\n\n## 归因排序\n"
            f"{root_lines}\n\n"
            f"## 对商品级广告的影响\n"
            f"- 若 GMV、CTR 或 CVR 走弱，商品作为主推品的投放优先级需要重新评估。\n"
            f"- 若退款率升高，应降低加价上限或先进入 ROI guardrail/智能调价保护。\n"
            f"- 商品级广告决策需要把经营归因结果与主推品评分、CPC 出价区间和"
            f"Query-SKU 召回质量一起判断。"
        )

    def _format_evidence_sources(self, state: AgentState) -> str:
        """Format RAG evidence sources for ad reports."""

        evidence_sources = self._collect_evidence_sources(state.retrieved_docs)
        return ", ".join(evidence_sources) if evidence_sources else "未检索到足够知识证据"

    def _collect_evidence_sources(self, docs: list[dict[str, Any]]) -> list[str]:
        """Collect unique evidence source names in display order."""

        sources: list[str] = []
        for doc in docs:
            source = doc.get("source", "")
            if source and source not in sources:
                sources.append(source)
        return sources

    def _safe_retrieved_docs(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return retrieved docs with sanitized content for LLM input."""

        safe_docs: list[dict[str, Any]] = []
        for doc in docs:
            safe_doc = dict(doc)
            sanitized_content = safe_doc.get("sanitized_content")
            if sanitized_content:
                safe_doc["content"] = sanitized_content
            safe_docs.append(safe_doc)
        return safe_docs

    def _build_rag_security_note(self, state: AgentState) -> str:
        """Render a compact RAG security note when cleanup happened."""

        rag_security = state.tool_results.get("rag_security", {})
        if not rag_security:
            return ""
        return " 已对检索上下文进行安全清洗。"

    def _build_contribution_summary(self, gmv_contribution: dict[str, Any]) -> str:
        """Render GMV driver contribution text when the tool result exists."""

        factor_effects = gmv_contribution.get("factor_effects", [])
        if not factor_effects:
            return ""

        top_negative_factors = gmv_contribution.get("top_negative_factors", [])
        top_negative = [
            item
            for factor in top_negative_factors
            for item in factor_effects
            if item["factor"] == factor
        ][:2]
        if not top_negative:
            top_negative = sorted(
                factor_effects,
                key=lambda item: item.get("normalized_abs_share", 0),
                reverse=True,
            )[:2]

        factor_lines = "\n".join(
            (
                f"- {item.get('factor_name', item.get('factor'))}："
                f"基准 {item.get('baseline', 0)}，当前 {item.get('current', 0)}，"
                f"估算影响 {item.get('effect', 0):+.2f}，"
                f"归一化贡献 {item.get('normalized_abs_share', 0) * 100:.2f}%。"
            )
            for item in factor_effects
        )
        top_text = "、".join(
            f"{item.get('factor_name', item.get('factor'))} {item.get('effect', 0):+.2f}"
            for item in top_negative
        )
        return (
            f"## GMV 贡献度分解\n"
            f"- 公式：{gmv_contribution.get('formula', 'GMV ≈ exposure × CTR × CVR × AOV')}。\n"
            f"- 估算 GMV 变化 {gmv_contribution.get('estimated_delta', 0):+.2f}，"
            f"真实 GMV 变化 {gmv_contribution.get('actual_delta', 0):+.2f}；"
            f"这是近似拆解，estimated_gmv 与真实订单 GMV 的差异需要看 residual。\n"
            f"{factor_lines}\n"
            f"- Top 负向因素：{top_text or '暂无明显负向因素'}。\n"
            f"- 小结：{str(gmv_contribution.get('summary', '待确认')).rstrip('。')}。\n\n"
        )

    def _build_primary_contribution_text(self, gmv_contribution: dict[str, Any]) -> str:
        """Prioritize the strongest GMV decomposition factor in attribution."""

        factor_effects = gmv_contribution.get("factor_effects", [])
        top_negative_factors = gmv_contribution.get("top_negative_factors", [])
        primary = next(
            (
                item
                for factor in top_negative_factors
                for item in factor_effects
                if item.get("factor") == factor
            ),
            None,
        )
        if primary:
            return (
                f"GMV 下滑的首要贡献因素是{primary.get('factor_name')}，"
                f"估算影响 {primary.get('effect', 0):+.2f}；"
                f"{primary.get('interpretation', '')}。"
                f"同时 search 渠道点击率明显走弱，说明商品在搜索场景的吸引力下降。\n"
            )
        return (
            "GMV 下滑的直接信号是订单规模下降，同时 search 渠道点击率明显走弱，"
            "说明商品在搜索场景的吸引力下降。\n"
        )

    def _build_review_summary(
        self,
        review_analysis: dict[str, Any],
        review_period_comparison: dict[str, Any],
    ) -> str:
        """Render review topic summary when review analysis is available."""

        if not review_analysis:
            return ""

        topic_distribution = review_analysis.get("topic_distribution", [])
        topics = review_analysis.get("topics", [])
        display_topics = topic_distribution or topics
        topic_text = "、".join(
            f"{topic.get('topic') or topic.get('label')}("
            f"{topic.get('count', topic.get('negative_review_count', 0))}条)"
            for topic in display_topics[:3]
        )
        rating_change = review_period_comparison.get("changes", {}).get("avg_rating", {})
        negative_rate_change = review_period_comparison.get("changes", {}).get(
            "negative_review_rate",
            {},
        )
        avg_rating = review_analysis.get(
            "avg_rating",
            review_analysis.get("average_rating", 0),
        )
        return (
            f"- Review Tool 评论分析：当前期评论 {review_analysis.get('review_count', 0)} 条，"
            f"平均评分 {avg_rating:.2f}，"
            f"差评 {review_analysis.get('negative_review_count', 0)} 条，"
            f"负面率 {_format_percent(review_analysis.get('negative_review_rate'))}，"
            f"高频主题为 {topic_text or '暂无足够主题证据'}。"
            f"评分变化 {rating_change.get('absolute_change', 0):+.2f}，"
            f"差评率变化 {negative_rate_change.get('absolute_change', 0) * 100:+.2f} 个百分点。\n"
        )

    def _build_campaign_summary(
        self,
        campaign_analysis: dict[str, Any],
        campaign_context_comparison: dict[str, Any],
    ) -> str:
        """Render campaign participation summary when campaign analysis is available."""

        if not campaign_analysis:
            return ""

        status = campaign_analysis.get("participation_status", "unknown")
        risk_level = campaign_analysis.get("risk_level", "unknown")
        current_count = campaign_analysis.get("eligible_campaign_count", 0)
        baseline_count = (
            campaign_context_comparison.get("baseline", {}).get("eligible_campaign_count", 0)
            if campaign_context_comparison
            else 0
        )
        return (
            f"- Campaign Tool 活动参与分析：当前期匹配活动 {current_count} 个，"
            f"基准期匹配活动 {baseline_count} 个，参与状态为 {status}，"
            f"风险等级 {risk_level}；{campaign_analysis.get('risk_reason', '')}\n"
        )

    def _build_review_attribution_text(self, review_analysis: dict[str, Any]) -> str:
        """Render attribution text backed by Review Tool."""

        top_topics = review_analysis.get("top_topics", [])
        if top_topics:
            return (
                f"Review Tool 显示差评主题集中在{'、'.join(top_topics[:3])}，"
                "说明售后和使用体验风险可能压低转化并推高退款。\n"
            )
        return "Review Tool 暂未发现足够集中的差评主题，售后/体验风险仍需继续观察。\n"

    def _build_campaign_attribution_text(self, campaign_analysis: dict[str, Any]) -> str:
        """Render attribution text backed by Campaign Tool."""

        if not campaign_analysis:
            return "其他运营因素需要补充证据后再判断。\n"
        if campaign_analysis.get("risk_level") == "high":
            return (
                "Campaign Tool 显示活动参与不足风险为 high，说明类目有活动机会但商品承接不足，"
                "可能削弱价格竞争力并放大 CTR/CVR 压力。\n"
            )
        return (
            "Campaign Tool 未发现明确高风险活动参与不足信号，活动影响需要结合运营报名数据待确认。\n"
        )

    def _build_peer_summary(self, state: AgentState) -> str:
        """Render a compact peer-product comparison sentence when available."""

        peer_results = state.tool_results.get("peer_period_comparisons", {})
        if not peer_results:
            return ""

        peer_parts = []
        for product_id, comparison in peer_results.items():
            gmv = _metric_change(comparison, "gmv")
            peer_parts.append(
                f"{product_id} GMV 变化率 {_format_percent_change(gmv.get('percent_change'))}"
            )
        return " 对比商品参考：" + "；".join(peer_parts) + "。"

    def _build_uncertainty_note(self, query: str) -> str:
        """Render a note when the user explicitly asks about conflicting evidence."""

        conflict_terms = ("冲突", "不一致", "相反", "矛盾")
        if not any(term in query for term in conflict_terms):
            return ""
        return (
            " 当前问题包含证据冲突信号，活动参与、运营口径和指标结果"
            "需要交叉核验，结论应标记为待确认。"
        )
