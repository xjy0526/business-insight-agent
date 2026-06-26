"""Claim-level evidence checks for generated diagnosis reports."""

from __future__ import annotations

import re
from typing import Any

from app.agent.state import AgentState

REQUIRED_REPORT_SECTIONS = ["问题概述", "指标拆解", "主要归因", "证据来源", "优化建议"]
ABSOLUTE_CLAIM_TERMS = [
    "唯一原因",
    "完全由于",
    "已经确认",
    "必然",
    "一定",
    "直接证明",
    "无需进一步验证",
]
CLAIM_TYPE_RULES = {
    "gmv": ["GMV", "成交", "订单"],
    "traffic": ["点击率", "CTR", "search", "搜索"],
    "conversion": ["转化率", "CVR"],
    "after_sales": ["退款", "售后", "差评", "物流", "续航", "佩戴"],
    "campaign": ["活动", "满减", "价格竞争力", "优惠"],
}
CLAIM_TYPE_EVIDENCE = {
    "gmv": {
        "tool_keys": ["current_gmv", "baseline_gmv", "period_comparison", "gmv_decomposition"],
        "sources": [],
    },
    "traffic": {
        "tool_keys": [
            "current_channel_breakdown",
            "baseline_channel_breakdown",
            "period_comparison",
        ],
        "sources": [],
    },
    "conversion": {
        "tool_keys": [
            "current_traffic",
            "baseline_traffic",
            "period_comparison",
            "gmv_decomposition",
        ],
        "sources": [],
    },
    "after_sales": {
        "tool_keys": [
            "current_refund",
            "baseline_refund",
            "review_analysis",
            "review_period_comparison",
        ],
        "sources": ["after_sales_policy.md", "review_analysis_guide.md"],
    },
    "campaign": {
        "tool_keys": ["campaign_participation", "campaign_context_comparison"],
        "sources": ["campaign_rules.md"],
    },
}
LEGACY_TOOL_KEY_ALIASES = {
    "gmv_contribution": "gmv_decomposition",
    "review_topic_analysis": "review_analysis",
    "campaign_analysis": "campaign_participation",
}


class EvidenceChecker:
    """Check report structure, claim support, numeric consistency, and unsafe certainty."""

    def check(self, state: AgentState) -> dict[str, Any]:
        """Compatibility wrapper used by the Agent node."""

        return self.run(state.diagnosis or "", state.tool_results, state.retrieved_docs)

    def check_report_structure(self, report: str) -> dict[str, Any]:
        """Check whether the report contains all required sections."""

        missing_sections = [
            section for section in REQUIRED_REPORT_SECTIONS if section not in report
        ]
        return {
            "pass": not missing_sections,
            "missing_sections": missing_sections,
        }

    def extract_claims(self, report: str) -> list[dict[str, Any]]:
        """Extract attribution claims from the `主要归因` section using simple rules."""

        attribution_section = self._extract_section(report, "主要归因")
        claims: list[dict[str, Any]] = []
        for line in attribution_section.splitlines():
            line = line.strip()
            match = re.match(r"^(?:\d+[.、]|[-*])\s*(.+)$", line)
            if not match:
                continue
            text = match.group(1).strip()
            for sentence in self._split_claim_line(text):
                if len(sentence) < 8:
                    continue
                claim_type, keywords = self._classify_claim(sentence)
                claims.append(
                    {
                        "claim_id": f"claim_{len(claims) + 1:03d}",
                        "text": sentence,
                        "claim_type": claim_type,
                        "keywords": keywords,
                    }
                )
        return claims

    def map_claim_to_evidence(
        self,
        claim: dict[str, Any],
        tool_results: dict[str, Any],
        retrieved_docs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Map one claim to supporting tool results or RAG sources."""

        claim_type = str(claim.get("claim_type", "general"))
        claim_text = str(claim.get("text", ""))
        retrieved_sources = {
            str(doc.get("source"))
            for doc in retrieved_docs
            if doc.get("source")
        }
        normalized_tool_results = self._with_legacy_aliases(tool_results)
        evidence_rule = CLAIM_TYPE_EVIDENCE.get(claim_type)
        issues: list[str] = []

        if claim_type == "general" or evidence_rule is None:
            supporting_keys = list(normalized_tool_results.keys())[:5]
            supporting_sources = sorted(retrieved_sources)[:5]
            supported = bool(supporting_keys or supporting_sources)
            return {
                "claim_id": claim.get("claim_id", ""),
                "claim_type": claim_type,
                "supported": supported,
                "evidence_type": self._evidence_types(supporting_keys, supporting_sources),
                "supporting_keys": supporting_keys,
                "supporting_sources": supporting_sources,
                "confidence": "medium" if supported else "low",
                "issues": [] if supported else ["general claim 缺少任意工具或 RAG 证据。"],
            }

        required_tool_keys = evidence_rule["tool_keys"]
        required_sources = evidence_rule["sources"]
        supporting_keys = [key for key in required_tool_keys if key in normalized_tool_results]
        supporting_sources = [
            source for source in required_sources if source in retrieved_sources
        ]

        if claim_type == "traffic" and any(term in claim_text for term in ("search", "搜索")):
            if not self._has_search_channel(normalized_tool_results):
                issues.append("claim 提到 search/搜索，但 channel_breakdown 中未找到 search 渠道。")
                supporting_keys = [
                    key
                    for key in supporting_keys
                    if key not in {"current_channel_breakdown", "baseline_channel_breakdown"}
                ]

        supported = bool(supporting_keys or supporting_sources) and not issues
        if not supported and not issues:
            issues.append(
                f"{claim_type} claim 缺少证据，需要工具 {required_tool_keys}"
                f" 或 RAG 来源 {required_sources}。"
            )

        return {
            "claim_id": claim.get("claim_id", ""),
            "claim_type": claim_type,
            "supported": supported,
            "evidence_type": self._evidence_types(supporting_keys, supporting_sources),
            "supporting_keys": supporting_keys,
            "supporting_sources": supporting_sources,
            "confidence": "high" if supported else "low",
            "issues": issues,
        }

    def check_numeric_consistency(
        self,
        report: str,
        tool_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Lightly check whether reported percentages can be found in tool outputs."""

        report_percentages = [
            float(match.group(1))
            for match in re.finditer(r"([+-]?\d+(?:\.\d+)?)%", report)
        ]
        tool_percent_candidates = self._collect_numeric_percent_candidates(tool_results)
        warnings = []
        for percentage in report_percentages:
            if not any(abs(percentage - candidate) <= 0.5 for candidate in tool_percent_candidates):
                warnings.append(f"报告中的百分比 {percentage:.2f}% 未在工具结果中找到近似值。")

        return {
            "pass": True,
            "warnings": warnings,
        }

    def check_unsupported_absolute_claims(
        self,
        report: str,
        evidence_available: bool,
    ) -> dict[str, Any]:
        """Detect unsafe absolute wording when evidence is not enough."""

        forbidden_terms_found = []
        if not evidence_available:
            forbidden_terms_found = [term for term in ABSOLUTE_CLAIM_TERMS if term in report]
        return {
            "pass": not forbidden_terms_found,
            "forbidden_terms_found": forbidden_terms_found,
        }

    def run(
        self,
        report: str,
        tool_results: dict[str, Any],
        retrieved_docs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run all evidence checks and return an eval-friendly reflection result."""

        structure_check = self.check_report_structure(report)
        claims = self.extract_claims(report)
        claim_checks = [
            {
                **claim,
                **self.map_claim_to_evidence(claim, tool_results, retrieved_docs),
            }
            for claim in claims
        ]
        numeric_consistency = self.check_numeric_consistency(report, tool_results)
        supported_claim_count = sum(1 for check in claim_checks if check["supported"])
        evidence_available = bool(tool_results or retrieved_docs) and (
            bool(claim_checks) and supported_claim_count == len(claim_checks)
        )
        unsupported_absolute_claims = self.check_unsupported_absolute_claims(
            report,
            evidence_available,
        )
        overall_confidence = self._overall_confidence(claim_checks)

        issues: list[str] = []
        suggestions: list[str] = []
        for section in structure_check["missing_sections"]:
            issues.append(f"诊断报告缺少“{section}”部分。")
        if not tool_results:
            issues.append("缺少指标或业务工具调用结果。")
            suggestions.append("补充 metrics、review、campaign 等工具调用。")
        if not retrieved_docs:
            issues.append("缺少 RAG 检索证据。")
            suggestions.append("补充 search_business_knowledge 检索活动、售后、运营和评价知识。")
        if not claim_checks:
            issues.append("主要归因部分未提取到可校验 claim。")
            suggestions.append("将主要归因写成 1.、2. 或 - 开头的明确结论。")

        for check in claim_checks:
            if check["supported"]:
                continue
            issues.append(f"{check['claim_id']} 缺少证据：{check['text']}")
            suggestions.extend(self._suggestions_for_claim_type(check["claim_type"]))

        if not unsupported_absolute_claims["pass"]:
            terms = "、".join(unsupported_absolute_claims["forbidden_terms_found"])
            issues.append(f"证据不足时出现绝对化表达：{terms}。")
            suggestions.append("将唯一、必然、已经确认等措辞改为“可能”“待确认”。")

        return {
            "pass": not issues,
            "structure_check": structure_check,
            "claims": claims,
            "claim_checks": claim_checks,
            "evidence_checks": claim_checks,
            "numeric_consistency": numeric_consistency,
            "unsupported_absolute_claims": unsupported_absolute_claims,
            "overall_confidence": overall_confidence,
            "issues": list(dict.fromkeys(issues)),
            "suggestions": list(dict.fromkeys(suggestions)),
        }

    def _extract_section(self, report: str, section_name: str) -> str:
        """Extract one markdown section by heading name."""

        pattern = rf"##\s*{re.escape(section_name)}\s*(.*?)(?:\n##\s|\Z)"
        match = re.search(pattern, report, flags=re.DOTALL)
        return match.group(1).strip() if match else ""

    def _split_claim_line(self, text: str) -> list[str]:
        """Split one attribution bullet into smaller claim sentences."""

        parts = re.split(r"(?<=[。；;])\s*", text)
        return [part.strip("。；; ") for part in parts if part.strip("。；; ")]

    def _classify_claim(self, text: str) -> tuple[str, list[str]]:
        """Classify claim type based on deterministic keyword rules."""

        if "GMV" in text and any(term in text for term in ("下滑", "变化", "贡献", "增长")):
            return "gmv", ["GMV"]

        matched_by_type = {
            claim_type: [keyword for keyword in keywords if keyword in text]
            for claim_type, keywords in CLAIM_TYPE_RULES.items()
        }
        matched_by_type = {
            claim_type: matched
            for claim_type, matched in matched_by_type.items()
            if matched
        }
        if matched_by_type:
            claim_type, matched = max(
                matched_by_type.items(),
                key=lambda item: len(item[1]),
            )
            return claim_type, matched
        return "general", []

    def _with_legacy_aliases(self, tool_results: dict[str, Any]) -> dict[str, Any]:
        """Expose legacy tool keys under the new evidence-check names."""

        normalized = dict(tool_results)
        for legacy_key, canonical_key in LEGACY_TOOL_KEY_ALIASES.items():
            if legacy_key in tool_results and canonical_key not in normalized:
                normalized[canonical_key] = tool_results[legacy_key]
        return normalized

    def _has_search_channel(self, tool_results: dict[str, Any]) -> bool:
        """Return whether channel breakdown results contain the search channel."""

        for key in ("current_channel_breakdown", "baseline_channel_breakdown"):
            channels = tool_results.get(key, {}).get("channels", [])
            if any(channel.get("channel") == "search" for channel in channels):
                return True
        return False

    def _evidence_types(
        self,
        supporting_keys: list[str],
        supporting_sources: list[str],
    ) -> list[str]:
        """Return evidence type labels for one claim check."""

        evidence_types = []
        if supporting_keys:
            evidence_types.append("tool_result")
        if supporting_sources:
            evidence_types.append("rag")
        return evidence_types

    def _collect_numeric_percent_candidates(self, value: Any, key_hint: str = "") -> list[float]:
        """Recursively collect numeric values that may appear as percentages in a report."""

        candidates: list[float] = []
        if isinstance(value, dict):
            for key, child in value.items():
                candidates.extend(self._collect_numeric_percent_candidates(child, str(key)))
            return candidates
        if isinstance(value, list):
            for child in value:
                candidates.extend(self._collect_numeric_percent_candidates(child, key_hint))
            return candidates
        if isinstance(value, bool) or not isinstance(value, int | float):
            return candidates

        numeric_value = float(value)
        ratio_key = any(
            term in key_hint.lower()
            for term in ("rate", "ctr", "cvr", "share", "percent", "change")
        )
        candidates.append(numeric_value)
        if ratio_key or abs(numeric_value) <= 10:
            candidates.append(numeric_value * 100)
        return candidates

    def _overall_confidence(self, claim_checks: list[dict[str, Any]]) -> str:
        """Derive overall confidence from supported claim ratio."""

        if not claim_checks:
            return "low"
        supported_count = sum(1 for check in claim_checks if check["supported"])
        if supported_count == len(claim_checks):
            return "high"
        if supported_count >= len(claim_checks) / 2:
            return "medium"
        return "low"

    def _suggestions_for_claim_type(self, claim_type: str) -> list[str]:
        """Return actionable suggestions for unsupported claims."""

        suggestions_by_type = {
            "gmv": ["补充工具：current_gmv、baseline_gmv、period_comparison、gmv_decomposition。"],
            "traffic": ["补充工具：current_channel_breakdown、baseline_channel_breakdown。"],
            "conversion": ["补充工具：current_traffic、baseline_traffic、period_comparison。"],
            "after_sales": [
                "补充工具：current_refund、baseline_refund、review_analysis、review_period_comparison。",
                "补充 RAG 来源：after_sales_policy.md、review_analysis_guide.md。",
            ],
            "campaign": [
                "补充工具：campaign_participation、campaign_context_comparison。",
                "补充 RAG 来源：campaign_rules.md。",
            ],
            "general": ["补充可追溯工具结果或 RAG 证据。"],
        }
        return suggestions_by_type.get(claim_type, suggestions_by_type["general"])
