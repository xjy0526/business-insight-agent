"""Fallback strategies for resilient Agent execution."""

from __future__ import annotations

from typing import Any

from app.agent.state import AgentState

RAG_EMPTY_MESSAGE = "未检索到足够知识证据"


class FallbackService:
    """Generate safe outputs when LLM, RAG, or metrics tools are unavailable."""

    def normalize_rag_result(self, result: dict[str, Any] | None, query: str) -> dict[str, Any]:
        """Return a non-crashing RAG result payload even when retrieval is empty."""

        if not result:
            return {"query": query, "results": [], "evidence_summary": RAG_EMPTY_MESSAGE}

        results = result.get("results") or []
        return {
            "query": result.get("query", query),
            "results": results,
            "evidence_summary": result.get("evidence_summary") or RAG_EMPTY_MESSAGE,
        }

    def generate_diagnosis_report(self, state: AgentState) -> str:
        """Generate a rule-based diagnosis report when model/tool output is incomplete."""

        metrics_failure_reason = self._metrics_failure_reason(state)
        evidence_summary = self._evidence_summary(state)
        product_label = state.entity_id or "目标商品"

        if metrics_failure_reason:
            metric_section = (
                f"指标工具未能完成分析，数据分析失败原因：{metrics_failure_reason}。"
                "当前报告只能基于用户问题、已成功的工具结果和知识库证据给出降级判断。"
            )
        else:
            comparison = state.tool_results.get("period_comparison", {})
            changes = comparison.get("changes", {})
            gmv = changes.get("gmv", {})
            ctr = changes.get("ctr", {})
            cvr = changes.get("cvr", {})
            refund_rate = changes.get("refund_rate", {})
            metric_section = (
                f"GMV 当前值 {gmv.get('current', 0)}，基准值 {gmv.get('baseline', 0)}；"
                f"点击率当前值 {ctr.get('current', 0)}，基准值 {ctr.get('baseline', 0)}；"
                f"转化率当前值 {cvr.get('current', 0)}，基准值 {cvr.get('baseline', 0)}；"
                f"退款率当前值 {refund_rate.get('current', 0)}，"
                f"基准值 {refund_rate.get('baseline', 0)}。"
            )

        return (
            "## 问题概述\n"
            f"本次分析对象为 {product_label}，用户问题是“{state.user_query}”。"
            "当前使用规则模板生成降级诊断报告，确保系统在 LLM、RAG "
            "或指标工具不稳定时仍可返回可 review 的结果。\n\n"
            "## 指标拆解\n"
            f"{metric_section}\n\n"
            "## 主要归因\n"
            "在降级模式下，系统不会编造确定结论。可优先从 GMV、点击率、"
            "转化率、退款率、渠道拆解、活动参与、评价与售后问题排查。"
            "如果存在指标工具失败，应先恢复数据查询后再给出强归因。\n\n"
            "## 证据来源\n"
            f"{evidence_summary}\n\n"
            "## 优化建议\n"
            "1. 先修复失败的数据或知识检索链路，保证结论有指标和 evidence 支撑。\n"
            "2. 若 GMV 下滑，优先复核曝光、点击率、转化率、客单价和退款率。\n"
            "3. 若退款率或差评异常，继续排查物流、质量、描述不符和用户体验问题。\n"
            "4. 对真实线上服务，应为 LLM、RAG 和数据库工具设置 timeout、重试、限流和降级策略。"
        )

    def _metrics_failure_reason(self, state: AgentState) -> str:
        """Extract metrics tool failure messages from Agent errors."""

        failures = [
            error.get("error", "")
            for error in state.errors
            if error.get("node") == "metrics_tool_node"
        ]
        return "；".join(filter(None, failures))

    def _evidence_summary(self, state: AgentState) -> str:
        """Summarize available RAG evidence or return the empty-evidence message."""

        if not state.retrieved_docs:
            return RAG_EMPTY_MESSAGE

        sources = []
        for doc in state.retrieved_docs:
            source = doc.get("source")
            if source and source not in sources:
                sources.append(source)

        return "RAG 证据来源：" + "、".join(sources) if sources else RAG_EMPTY_MESSAGE
