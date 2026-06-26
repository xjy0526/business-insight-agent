"""Security guardrails for prompt, tool, SQL, and output safety."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

PROMPT_INJECTION_REMOVED = "[POTENTIAL_PROMPT_INJECTION_REMOVED]"

INJECTION_PATTERNS: dict[str, tuple[str, str]] = {
    "ignore_previous_instructions": (
        r"忽略(以上|之前|所有).{0,16}(规则|指令|提示|system|系统)"
        r"|ignore\s+(all\s+)?previous\s+(instructions|rules)"
        r"|ignore\s+all\s+previous",
        "medium",
    ),
    "system_prompt_request": (
        r"system\s+prompt|输出(你的)?系统提示词|系统提示词",
        "high",
    ),
    "developer_message_request": (
        r"developer\s+message|开发者(消息|指令)|developer\s+instruction",
        "high",
    ),
    "reveal_prompt": (
        r"reveal\s+your\s+prompt|(输出|泄露|展示|打印).{0,12}(prompt|提示词|系统提示词)",
        "high",
    ),
    "destructive_database_instruction": (
        r"删除数据库|drop\s+table|执行危险\s*sql|\b(drop|delete|truncate|alter)\b",
        "high",
    ),
    "unauthorized_tool_call": (
        r"调用未授权工具|unauthorized\s+tool|未授权.{0,8}工具",
        "high",
    ),
    "role_override": (
        r"你现在不是|你现在是|扮演.{0,16}(系统|开发者|root|管理员)",
        "medium",
    ),
    "document_override": (
        r"你必须听从文档|文档.{0,12}(覆盖|优先于|高于).{0,12}(系统|指令)",
        "medium",
    ),
    "override_instruction": (
        r"override\s+instruction",
        "medium",
    ),
    "bypass_safety": (
        r"bypass\s+safety|绕过.{0,12}(安全|safety|工具|限制)",
        "high",
    ),
    "forced_unsupported_answer": (
        r"(直接说|只说|输出).{0,20}(唯一原因|唯一的原因)",
        "medium",
    ),
    "secret_request": (
        r"(api[_ -]?key|密钥|token|密码|环境变量|bearer\s+[A-Za-z0-9._~+/=-]{8,})",
        "high",
    ),
}

ALLOWED_TOOLS = {
    "get_product_basic_info",
    "compare_periods",
    "calculate_gmv",
    "calculate_traffic_metrics",
    "calculate_refund_rate",
    "calculate_aov",
    "analyze_channel_breakdown",
    "decompose_gmv_change",
    "analyze_review_topics",
    "compare_review_periods",
    "check_campaign_participation",
    "compare_campaign_context",
    "search_business_knowledge",
    "reflection_checker",
}

SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "DASHSCOPE_API_KEY",
    "LLM_API_KEY",
    "QWEN_API_KEY",
)


@dataclass(frozen=True)
class PromptGuardResult:
    """Normalized prompt-guard decision."""

    risk_level: str
    detected_patterns: list[str]
    sanitized_query: str
    action: str
    is_injection: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "risk_level": self.risk_level,
            "detected_patterns": self.detected_patterns,
            "matched_patterns": self.detected_patterns,
            "is_injection": self.is_injection,
            "sanitized_query": self.sanitized_query,
            "sanitized_text": self.sanitized_query,
            "action": self.action,
        }


class SecurityService:
    """Central security policy service used by Agent, RAG, SQL, and reports."""

    def detect_prompt_injection(self, text: str) -> dict[str, Any]:
        """Detect prompt-injection or unsafe instruction patterns in text."""

        matched_patterns = [
            name
            for name, (pattern, _risk) in INJECTION_PATTERNS.items()
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]
        if any(INJECTION_PATTERNS[name][1] == "high" for name in matched_patterns):
            risk_level = "high"
        elif matched_patterns:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "matched_patterns": matched_patterns,
            "is_injection": bool(matched_patterns),
            "sanitized_text": self.sanitize_untrusted_context(text)
            if matched_patterns
            else text,
        }

    def sanitize_untrusted_context(self, text: str) -> str:
        """Mark or remove injection fragments while preserving business content."""

        sanitized = text
        for pattern, _risk in INJECTION_PATTERNS.values():
            sanitized = re.sub(
                pattern,
                PROMPT_INJECTION_REMOVED,
                sanitized,
                flags=re.IGNORECASE,
            )
        sanitized = re.sub(
            rf"({re.escape(PROMPT_INJECTION_REMOVED)}[\s,，。；;]*)+",
            PROMPT_INJECTION_REMOVED,
            sanitized,
        )
        return sanitized.strip()

    def sanitize_user_query(self, query: str) -> str:
        """Remove injected instruction clauses while preserving the business question."""

        if not query.strip():
            return query

        fragments = re.split(r"[。！？!?；;]\s*", query)
        safe_fragments: list[str] = []
        for fragment in fragments:
            fragment = fragment.strip()
            if not fragment:
                continue
            fragment_has_injection = any(
                re.search(pattern, fragment, flags=re.IGNORECASE)
                for pattern, _risk in INJECTION_PATTERNS.values()
            )
            cleaned = self.sanitize_untrusted_context(fragment)
            cleaned = cleaned.replace(PROMPT_INJECTION_REMOVED, "").strip(" ，,。；;")
            has_business_anchor = bool(
                re.search(
                    r"\bP\d{4}\b|GMV|退款率|点击率|转化率|差评|评价|经营|下滑|下降",
                    cleaned,
                    flags=re.IGNORECASE,
                )
            )
            if fragment_has_injection and not has_business_anchor:
                continue
            if cleaned:
                safe_fragments.append(cleaned)

        sanitized = "。".join(safe_fragments)
        sanitized = re.sub(r"\s+", " ", sanitized).strip(" ，,。；;")
        return sanitized or query

    def validate_tool_name(self, tool_name: str) -> dict[str, Any]:
        """Validate a tool call against the Agent tool allowlist."""

        if tool_name in ALLOWED_TOOLS:
            return {
                "allowed": True,
                "reason": f"Tool `{tool_name}` is in the allowlist.",
            }
        return {
            "allowed": False,
            "reason": f"Tool `{tool_name}` is not in the allowlist.",
        }

    def validate_sql_query(self, sql: str) -> dict[str, Any]:
        """Validate SQL for security auditing without executing it."""

        try:
            from app.tools.sql_tool import _validate_readonly_sql

            _validate_readonly_sql(sql)
        except ValueError as error:
            reason = str(error)
            high_risk_terms = ("Dangerous SQL keyword", "Only one SELECT")
            risk_level = "high" if any(term in reason for term in high_risk_terms) else "medium"
            return {
                "allowed": False,
                "risk_level": risk_level,
                "reason": reason,
            }

        return {
            "allowed": True,
            "risk_level": "low",
            "reason": "Only a single read-only SELECT query is allowed.",
        }

    def filter_sensitive_output(self, text: str) -> str:
        """Redact API keys and bearer tokens from user-visible output."""

        filtered = text
        for env_name in SECRET_ENV_NAMES:
            value = os.getenv(env_name)
            if value:
                filtered = filtered.replace(value, "[FILTERED_SECRET]")

        secret_patterns = [
            r"sk-[A-Za-z0-9_-]{8,}",
            r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
            r"(OPENAI_API_KEY|DASHSCOPE_API_KEY|LLM_API_KEY|QWEN_API_KEY)\s*=\s*['\"]?[^'\"\s;]+",
        ]
        for pattern in secret_patterns:
            filtered = re.sub(
                pattern,
                lambda match: (
                    f"{match.group(1)}=[FILTERED_SECRET]"
                    if match.lastindex
                    else "[FILTERED_SECRET]"
                ),
                filtered,
                flags=re.IGNORECASE,
            )
        return filtered


class PromptInjectionGuard:
    """Detect and neutralize prompt-injection text in user questions."""

    def __init__(self, security: SecurityService | None = None) -> None:
        self.security = security or SecurityService()

    def analyze(self, query: str) -> PromptGuardResult:
        """Analyze one user query and return a safe query for downstream prompts."""

        detection = self.security.detect_prompt_injection(query)
        detected_patterns = list(detection["matched_patterns"])
        sanitized_query = (
            self.security.sanitize_user_query(query) if detected_patterns else query
        )
        action = "ignore_injected_instructions" if detected_patterns else "allow"
        return PromptGuardResult(
            risk_level=str(detection["risk_level"]),
            detected_patterns=detected_patterns,
            sanitized_query=sanitized_query,
            action=action,
            is_injection=bool(detection["is_injection"]),
        )
