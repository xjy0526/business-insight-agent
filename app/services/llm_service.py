"""LLM service abstraction with a deterministic local mock provider."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings


class LLMService:
    """Generate text or JSON through a configured LLM provider.

    The current implementation keeps local development reliable by using mock
    responses when provider is "mock" or when a real provider has no API key.
    OpenAI and Qwen adapter methods are intentionally isolated for future work.
    """

    def __init__(self, provider: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.provider = (provider or settings.llm_provider or "mock").lower()
        self.api_key = api_key if api_key is not None else settings.llm_api_key

    @property
    def uses_mock(self) -> bool:
        """Return whether this instance should use deterministic mock output."""

        return self.provider == "mock" or not self.api_key

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> str:
        """Generate text from a prompt.

        OpenAI and Qwen are reserved as provider names. Until concrete API
        adapters are configured, missing credentials or unsupported providers
        fall back to mock output instead of failing local tests.
        """

        if self.uses_mock:
            return self._generate_mock(prompt)

        if self.provider == "openai":
            return self._generate_openai(prompt, temperature, timeout)
        if self.provider == "qwen":
            return self._generate_qwen(prompt, temperature, timeout)

        return self._generate_mock(prompt)

    def generate_json(self, prompt: str, timeout: float | None = None) -> dict[str, Any]:
        """Generate a response and parse it as JSON with safe fallback."""

        text = self.generate(prompt, timeout=timeout)

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            json_text = self._extract_json_object(text)
            if json_text is not None:
                try:
                    parsed = json.loads(json_text)
                    return parsed if isinstance(parsed, dict) else {"value": parsed}
                except json.JSONDecodeError as error:
                    return {"raw_text": text, "parse_error": str(error)}

            return {"raw_text": text, "parse_error": "No JSON object found in model output."}

    def _generate_openai(
        self,
        prompt: str,
        temperature: float,
        timeout: float | None,
    ) -> str:
        """Reserved OpenAI adapter entrypoint."""

        return self._generate_mock(prompt)

    def _generate_qwen(
        self,
        prompt: str,
        temperature: float,
        timeout: float | None,
    ) -> str:
        """Reserved Qwen adapter entrypoint."""

        return self._generate_mock(prompt)

    def _generate_mock(self, prompt: str) -> str:
        """Return deterministic mock output based on the prompt intent."""

        if "意图识别器" in prompt or "need_tools" in prompt:
            return json.dumps(self._mock_intent_response(prompt), ensure_ascii=False)

        if "任务规划器" in prompt or "plan_steps" in prompt:
            return json.dumps(self._mock_plan_response(prompt), ensure_ascii=False)

        if "反思校验器" in prompt or '"pass"' in prompt:
            return json.dumps(
                {"pass": True, "issues": [], "suggestions": []},
                ensure_ascii=False,
            )

        return self._mock_diagnosis_report(prompt)

    def _mock_intent_response(self, prompt: str) -> dict[str, Any]:
        """Recognize a small set of business intents for local tests."""

        query = self._extract_user_query(prompt)
        normalized_query = query.upper()
        entity_id = self._extract_product_id(query)
        traffic_terms = ("点击率", "转化率")

        if "差评" in query or "评价" in query:
            intent = "review_analysis"
            metric = "review"
            need_tools = ["search_business_knowledge"]
        elif (
            "GMV" in normalized_query
            or "经营表现" in query
            or "经营分析" in query
            or "经营异常" in query
            or "活动" in query
            or "价格竞争力" in query
        ):
            intent = "business_diagnosis"
            metric = "gmv"
            need_tools = [
                "get_product_basic_info",
                "compare_periods",
                "analyze_channel_breakdown",
                "search_business_knowledge",
            ]
        elif "退款率" in query:
            intent = "refund_analysis"
            metric = "refund_rate"
            need_tools = [
                "calculate_refund_rate",
                "search_business_knowledge",
            ]
        elif (
            any(term in query for term in traffic_terms)
            or "CTR" in normalized_query
            or "CVR" in normalized_query
        ):
            intent = "traffic_analysis"
            metric = "ctr" if "点击率" in query or "CTR" in normalized_query else "cvr"
            need_tools = [
                "calculate_traffic_metrics",
                "analyze_channel_breakdown",
                "search_business_knowledge",
            ]
        else:
            intent = "unknown"
            metric = "unknown"
            need_tools = ["search_business_knowledge"]

        return {
            "intent": intent,
            "entity_type": "product" if entity_id else "unknown",
            "entity_id": entity_id,
            "metric": metric,
            "time_range": {
                "current_start": "2026-04-01",
                "current_end": "2026-04-30",
                "baseline_start": "2026-03-01",
                "baseline_end": "2026-03-31",
            },
            "need_tools": need_tools,
        }

    def _mock_plan_response(self, prompt: str) -> dict[str, Any]:
        """Return a compact deterministic task plan."""

        intent = "business_diagnosis"
        if "refund_analysis" in prompt:
            intent = "refund_analysis"
        elif "traffic_analysis" in prompt:
            intent = "traffic_analysis"

        plan_steps = [
            {
                "step_id": 1,
                "name": "识别商品与时间范围",
                "tool": "get_product_basic_info",
                "purpose": "确认分析对象、类目、价格和品牌。",
            },
            {
                "step_id": 2,
                "name": "计算核心指标变化",
                "tool": "compare_periods",
                "purpose": f"对 {intent} 所需指标进行当前期与基准期对比。",
            },
            {
                "step_id": 3,
                "name": "检索业务知识证据",
                "tool": "search_business_knowledge",
                "purpose": "补充活动、售后、运营或评价分析依据。",
            },
            {
                "step_id": 4,
                "name": "生成并校验诊断报告",
                "tool": "reflection_checker",
                "purpose": "检查报告是否有证据支撑并给出可执行建议。",
            },
        ]
        return {"plan_steps": plan_steps}

    def _mock_diagnosis_report(self, prompt: str) -> str:
        """Return a structured Chinese diagnosis report for local development."""

        return (
            "## 问题概述\n"
            "基于当前输入，系统需要结合指标结果和 RAG 证据判断经营异常。\n\n"
            "## 指标拆解\n"
            "请重点查看 GMV、CTR、CVR、AOV、退款率和渠道拆解的当前期与基准期变化。\n\n"
            "## 主要归因\n"
            "仅能根据已提供的指标和知识证据提出归因；证据不足时应标注为待确认。\n\n"
            "## 证据来源\n"
            "证据应来自 metrics_tool 的计算结果和 RAG 知识库检索结果。\n\n"
            "## 优化建议\n"
            "建议围绕活动参与、价格竞争力、主图标题、物流履约、详情页承诺和售后策略逐项优化。"
        )

    def _extract_user_query(self, prompt: str) -> str:
        """Extract the user query from a Chinese prompt template when possible."""

        match = re.search(r"用户问题：\s*(.+?)(?:\n\n|\Z)", prompt, re.DOTALL)
        if match:
            return match.group(1).strip()
        return prompt

    def _extract_product_id(self, text: str) -> str:
        """Extract a product ID such as P1001 from text."""

        match = re.search(r"\bP\d{4}\b", text.upper())
        return match.group(0) if match else ""

    def _extract_json_object(self, text: str) -> str | None:
        """Extract the first balanced-looking JSON object from text."""

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1]
