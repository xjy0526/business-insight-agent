"""Diagnosis report generation service for BusinessInsight Agent."""

from __future__ import annotations

import json
from typing import Any

from app.agent.prompts import DIAGNOSIS_PROMPT
from app.agent.state import AgentState
from app.services.fallback_service import FallbackService
from app.services.llm_service import LLMService


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
            return self.fallback.generate_diagnosis_report(state)

        if not self.llm.uses_mock:
            report = self.llm.generate(
                DIAGNOSIS_PROMPT.format(
                    query=state.user_query,
                    metrics_result=json.dumps(
                        state.tool_results,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    rag_evidence=json.dumps(
                        state.retrieved_docs,
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            )
            if report.strip():
                return report
            return self.fallback.generate_diagnosis_report(state)

        return self.build_mock_diagnosis_report(state)

    def build_mock_diagnosis_report(self, state: AgentState) -> str:
        """Build a deterministic but business-like Chinese diagnosis report."""

        product = state.tool_results.get("product_basic_info", {})
        comparison = state.tool_results.get("period_comparison", {})
        current_gmv = state.tool_results.get("current_gmv", {})
        baseline_gmv = state.tool_results.get("baseline_gmv", {})
        current_refund = state.tool_results.get("current_refund", {})
        baseline_refund = state.tool_results.get("baseline_refund", {})
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
        peer_summary = self._build_peer_summary(state)
        uncertainty_note = self._build_uncertainty_note(state.user_query)

        return (
            f"## 问题概述\n"
            f"用户问题关注“{state.user_query}”。"
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
            f"## 主要归因\n"
            f"1. GMV 下滑的直接信号是订单规模下降，同时 search 渠道点击率明显走弱，"
            f"说明商品在搜索场景的吸引力下降。\n"
            f"2. 退款率明显升高，结合知识库中售后与评价指南，物流慢、续航不达预期、"
            f"佩戴不舒服等问题可能会同时压低转化并推高退款。\n"
            f"3. RAG 证据提示：平台活动参与不足会削弱价格竞争力；如果 P1001 "
            f"在 4 月活动中仅低曝光参与，则可能放大搜索 CTR 和 GMV 压力。\n\n"
            f"## 证据来源\n"
            f"- 指标工具：compare_periods、calculate_gmv、calculate_refund_rate、"
            f"analyze_channel_breakdown。\n"
            f"- RAG 文档：{evidence_source_text}。\n\n"
            f"## 优化建议\n"
            f"1. 优先复盘 P1001 的 4 月活动参与状态，争取进入音频类目主会场"
            f"或提高券曝光，修复价格竞争力。\n"
            f"2. 针对 search 点击率下降，重做主图利益点、标题关键词和到手价展示，"
            f"并和竞品搜索卡片对比。\n"
            f"3. 针对退款率升高，排查物流时效、续航描述、佩戴舒适度和批次质量，"
            f"必要时调整详情页承诺并推动供应链复检。\n"
            f"4. 持续监控 GMV、点击率、转化率、退款率和差评主题，按周验证优化动作是否有效。"
        )

    def _collect_evidence_sources(self, docs: list[dict[str, Any]]) -> list[str]:
        """Collect unique evidence source names in display order."""

        sources: list[str] = []
        for doc in docs:
            source = doc.get("source", "")
            if source and source not in sources:
                sources.append(source)
        return sources

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
