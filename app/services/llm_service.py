"""LLM service abstraction with a deterministic local mock provider."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app.config import get_settings

try:  # pragma: no cover - import failure is only relevant in stripped-down envs.
    import openai
except ImportError:  # pragma: no cover
    openai = None  # type: ignore[assignment]

SUPPORTED_PROVIDERS = {"mock", "openai", "qwen"}
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_QWEN_MODEL = "qwen-plus"
SYSTEM_MESSAGE = "你是一个严谨的电商经营分析 Agent，只能基于工具结果和证据回答。"


class LLMService:
    """Generate text or JSON through a configured LLM provider.

    Local development remains reliable by using mock responses when provider is
    "mock", credentials are missing, the OpenAI SDK is unavailable, or a real
    provider call fails. OpenAI and Qwen both use OpenAI-compatible chat
    completions.
    """

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        fallback_to_mock: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = (provider or settings.llm_provider or "mock").lower()
        self.api_key = self._blank_to_none(
            api_key if api_key is not None else self._resolve_api_key(settings.llm_api_key)
        )
        self.base_url = self._blank_to_none(
            base_url if base_url is not None else self._resolve_base_url(settings.llm_base_url)
        )
        self.model = (
            self._blank_to_none(model)
            or self._resolve_model(settings.llm_model)
            or self._default_model()
        )
        legacy_timeout = settings.llm_timeout_seconds
        self.timeout = timeout if timeout is not None else (legacy_timeout or settings.llm_timeout)
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.fallback_to_mock = (
            fallback_to_mock
            if fallback_to_mock is not None
            else settings.llm_fallback_to_mock
        )
        self.last_error: dict[str, str] | None = None
        self.provider_status = "not_called"
        self.status_code: int | None = None
        self.retry_count = 0
        self.token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    @property
    def uses_mock(self) -> bool:
        """Return whether this instance should use deterministic mock output."""

        return (
            self.provider == "mock"
            or self.provider not in SUPPORTED_PROVIDERS
            or (self.provider in {"openai", "qwen"} and not self.api_key)
            or (self.provider in {"openai", "qwen"} and openai is None)
        )

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> str:
        """Generate text from a prompt.

        Missing credentials, unavailable SDK, unsupported providers, or provider
        errors fall back to deterministic mock output when configured.
        """

        if self.uses_mock:
            output = self._generate_mock(prompt)
            self._record_mock_usage(prompt, output)
            return output

        if self.provider == "openai":
            return self._generate_openai(prompt, temperature, timeout)
        if self.provider == "qwen":
            return self._generate_qwen(prompt, temperature, timeout)

        return self._handle_provider_error(
            ValueError(f"Unsupported LLM provider: {self.provider}"),
            prompt,
        )

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
        """Call OpenAI's chat-completions-compatible API."""

        return self._generate_chat_completion(
            prompt=prompt,
            temperature=temperature,
            timeout=timeout,
            default_base_url=None,
            default_model=DEFAULT_OPENAI_MODEL,
        )

    def _generate_qwen(
        self,
        prompt: str,
        temperature: float,
        timeout: float | None,
    ) -> str:
        """Call Qwen/DashScope through the OpenAI-compatible API."""

        return self._generate_chat_completion(
            prompt=prompt,
            temperature=temperature,
            timeout=timeout,
            default_base_url=DEFAULT_QWEN_BASE_URL,
            default_model=DEFAULT_QWEN_MODEL,
        )

    def _generate_chat_completion(
        self,
        prompt: str,
        temperature: float,
        timeout: float | None,
        default_base_url: str | None,
        default_model: str,
    ) -> str:
        """Generate text through the OpenAI SDK chat completions interface."""

        if not self.api_key or openai is None:
            return self._generate_mock(prompt)

        model = self.model or default_model
        try:
            client = self._build_client(default_base_url=default_base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                timeout=timeout or self.timeout,
            )
            content = self._extract_message_content(response)
            if isinstance(content, str) and content.strip():
                self._record_provider_success(prompt, content, response)
                return content
            output = self._generate_mock(prompt)
            self._record_mock_usage(prompt, output, status="fallback_empty_content")
            return output
        except Exception as error:
            return self._handle_provider_error(error, prompt)

    def _build_client(self, default_base_url: str | None) -> Any:
        """Build an OpenAI SDK client without exposing credentials."""

        if openai is None:
            raise RuntimeError("openai package is unavailable.")

        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
        base_url = self.base_url or default_base_url
        if base_url:
            client_kwargs["base_url"] = base_url.rstrip("/")
        return openai.OpenAI(**client_kwargs)

    def _extract_message_content(self, response: Any) -> str:
        """Read choices[0].message.content from SDK or fake-client responses."""

        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices")
        if not choices:
            return ""

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None and isinstance(first_choice, dict):
            message = first_choice.get("message", {})
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        return content if isinstance(content, str) else ""

    def _handle_provider_error(self, error: Exception, prompt: str) -> str:
        """Record sanitized provider errors and optionally fallback to mock."""

        self.last_error = {
            "type": type(error).__name__,
            "message": self._sanitize_error_message(str(error)),
        }
        self.provider_status = "error"
        self.retry_count = self.max_retries
        if self.fallback_to_mock:
            output = self._generate_mock(prompt)
            self._record_mock_usage(prompt, output, status="fallback_error")
            return output
        raise error

    def provider_metadata(self) -> dict[str, Any]:
        """Return trace-safe LLM provider metadata without credentials."""

        metadata: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "uses_mock": self.uses_mock,
            "fallback_to_mock": self.fallback_to_mock,
            "provider_status": self.provider_status,
            "status_code": self.status_code,
            "retry_count": self.retry_count,
            "configured_max_retries": self.max_retries,
            "token_usage": self.token_usage,
        }
        if self.last_error:
            metadata["last_error"] = self.last_error
        return metadata

    def record_local_generation(
        self,
        prompt: str,
        content: str,
        status: str = "local_template",
    ) -> None:
        """Record local template/fallback generation in provider metadata."""

        self._record_mock_usage(prompt, content, status=status)

    def _record_provider_success(self, prompt: str, content: str, response: Any) -> None:
        """Record trace-safe provider status and token usage."""

        self.provider_status = "ok"
        self.status_code = self._extract_status_code(response)
        self.retry_count = 0
        self.token_usage = self._extract_usage(response) or self._estimate_usage(prompt, content)

    def _record_mock_usage(self, prompt: str, content: str, status: str = "mock") -> None:
        """Record estimated token usage for deterministic mock/fallback output."""

        self.provider_status = status
        self.status_code = None
        self.token_usage = self._estimate_usage(prompt, content)

    def _extract_usage(self, response: Any) -> dict[str, int] | None:
        """Extract token usage from SDK and fake-client responses."""

        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        if usage is None:
            return None

        prompt_tokens = self._usage_value(usage, "prompt_tokens")
        completion_tokens = self._usage_value(usage, "completion_tokens")
        total_tokens = self._usage_value(usage, "total_tokens")
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _usage_value(self, usage: Any, key: str) -> int:
        """Read one usage value without depending on SDK internals."""

        value = getattr(usage, key, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(key)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _extract_status_code(self, response: Any) -> int | None:
        """Extract provider status code when the SDK exposes it."""

        candidates = [
            getattr(response, "status_code", None),
            getattr(getattr(response, "response", None), "status_code", None),
            getattr(getattr(response, "_response", None), "status_code", None),
        ]
        for value in candidates:
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None

    def _estimate_usage(self, prompt: str, content: str) -> dict[str, int]:
        """Estimate token counts for local mock/fallback observability."""

        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(content) // 4)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def _sanitize_error_message(self, message: str) -> str:
        """Redact credential-like substrings from provider error messages."""

        if self.api_key:
            message = message.replace(self.api_key, "[redacted]")
        message = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-[redacted]", message)
        message = re.sub(
            r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*\S+",
            r"\1=[redacted]",
            message,
        )
        return message[:500]

    def _resolve_api_key(self, configured_api_key: str | None) -> str | None:
        """Resolve provider-specific API keys while keeping generic env support."""

        configured_api_key = self._blank_to_none(configured_api_key)
        if configured_api_key:
            return configured_api_key
        if self.provider == "openai":
            return os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if self.provider == "qwen":
            return (
                os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("QWEN_API_KEY")
                or os.getenv("LLM_API_KEY")
            )
        return os.getenv("LLM_API_KEY")

    def _resolve_base_url(self, configured_base_url: str | None) -> str | None:
        """Resolve provider base URL from settings or common compatible env vars."""

        return self._blank_to_none(
            configured_base_url or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        )

    def _resolve_model(self, configured_model: str | None) -> str | None:
        """Resolve provider model from settings or provider-specific env vars."""

        configured_model = self._blank_to_none(configured_model)
        if configured_model:
            return configured_model
        if self.provider == "openai":
            return self._blank_to_none(os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL"))
        if self.provider == "qwen":
            return self._blank_to_none(os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL"))
        return self._blank_to_none(os.getenv("LLM_MODEL"))

    def _default_model(self) -> str:
        """Return a provider-specific default model."""

        if self.provider == "openai":
            return DEFAULT_OPENAI_MODEL
        return DEFAULT_QWEN_MODEL

    def _blank_to_none(self, value: str | None) -> str | None:
        """Normalize empty strings from env files to None."""

        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

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

        if (
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
        elif "差评" in query or "评价" in query:
            intent = "review_analysis"
            metric = "review"
            need_tools = ["analyze_review_topics", "search_business_knowledge"]
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
            "建议围绕活动参与、价格竞争力、项目图标题、预约履约、详情页承诺和售后策略逐项优化。"
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
        """Extract JSON from markdown fences or the first balanced-looking object."""

        fenced_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if fenced_match:
            return fenced_match.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1]
