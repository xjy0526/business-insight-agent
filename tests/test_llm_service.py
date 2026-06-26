"""Tests for LLM service provider behavior."""

from types import SimpleNamespace

import pytest
from app.agent.prompts import INTENT_ROUTER_PROMPT
from app.services import llm_service
from app.services.llm_service import LLMService


def _fake_response(content: str, usage: SimpleNamespace | None = None) -> SimpleNamespace:
    """Build a minimal OpenAI SDK-like chat completion response."""

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage=usage,
    )


def test_mock_provider_without_api_key() -> None:
    """Mock provider should work without credentials."""

    service = LLMService(provider="mock", api_key="")
    result = service.generate_json(
        INTENT_ROUTER_PROMPT.format(query="商品 P1001 最近 GMV 为什么下降？")
    )

    assert service.uses_mock is True
    assert result["intent"] == "business_diagnosis"
    assert result["entity_id"] == "P1001"


def test_qwen_without_api_key_falls_back_to_mock() -> None:
    """Qwen provider should use mock when no API key is configured."""

    service = LLMService(provider="qwen", api_key="")

    assert service.uses_mock is True
    assert service.generate_json(INTENT_ROUTER_PROMPT.format(query="P1001 退款率异常"))[
        "intent"
    ] == "refund_analysis"


def test_openai_without_api_key_falls_back_to_mock() -> None:
    """OpenAI provider should use mock when no API key is configured."""

    service = LLMService(provider="openai", api_key="")

    assert service.uses_mock is True
    assert service.generate_json(INTENT_ROUTER_PROMPT.format(query="P1001 点击率下降"))[
        "intent"
    ] == "traffic_analysis"


def test_generate_json_extracts_markdown_json(monkeypatch) -> None:
    """JSON parser should support markdown-fenced JSON output."""

    service = LLMService(provider="mock")

    def fake_generate(prompt: str, temperature: float = 0.2, timeout: float | None = None) -> str:
        return '```json\n{"pass": true, "issues": []}\n```'

    monkeypatch.setattr(service, "generate", fake_generate)

    assert service.generate_json("reflection") == {"pass": True, "issues": []}


def test_real_provider_uses_openai_client_but_no_network(monkeypatch) -> None:
    """OpenAI adapter should call the SDK client and read a fake response."""

    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured["create_kwargs"] = kwargs
            return _fake_response("真实模型回答")

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_service.openai, "OpenAI", FakeOpenAI)
    service = LLMService(
        provider="openai",
        api_key="fake-key",
        model="gpt-test",
        base_url="https://example.test/v1",
        timeout=12,
        max_retries=1,
    )

    result = service._generate_openai("请分析 P1001", temperature=0.1, timeout=9)

    assert result == "真实模型回答"
    assert captured["client_kwargs"] == {
        "api_key": "fake-key",
        "timeout": 12,
        "max_retries": 1,
        "base_url": "https://example.test/v1",
    }
    assert captured["create_kwargs"]["model"] == "gpt-test"  # type: ignore[index]
    assert captured["create_kwargs"]["timeout"] == 9  # type: ignore[index]
    assert service.provider_metadata()["provider_status"] == "ok"
    assert service.provider_metadata()["token_usage"]["total_tokens"] > 0


def test_qwen_provider_uses_default_compatible_base_url(monkeypatch) -> None:
    """Qwen adapter should default to DashScope's OpenAI-compatible endpoint."""

    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured["create_kwargs"] = kwargs
            return _fake_response("Qwen 回答")

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_service.openai, "OpenAI", FakeOpenAI)
    service = LLMService(provider="qwen", api_key="fake-key", model="qwen-plus")

    result = service.generate("请分析 P1001")

    assert result == "Qwen 回答"
    assert (
        captured["client_kwargs"]["base_url"]  # type: ignore[index]
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert captured["create_kwargs"]["model"] == "qwen-plus"  # type: ignore[index]


def test_real_provider_error_fallback_to_mock(monkeypatch) -> None:
    """Provider errors should fallback or raise according to configuration."""

    class FailingCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            raise RuntimeError("provider down with sk-test-secret")

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=FailingCompletions())

    monkeypatch.setattr(llm_service.openai, "OpenAI", FakeOpenAI)
    service = LLMService(provider="openai", api_key="sk-test-secret", fallback_to_mock=True)

    result = service.generate("请生成诊断报告")

    assert "问题概述" in result
    assert service.last_error is not None
    assert "sk-test-secret" not in service.last_error["message"]
    assert service.provider_metadata()["provider_status"] == "fallback_error"
    assert service.provider_metadata()["retry_count"] == service.max_retries

    strict_service = LLMService(
        provider="openai",
        api_key="sk-test-secret",
        fallback_to_mock=False,
    )
    with pytest.raises(RuntimeError, match="provider down"):
        strict_service.generate("请生成诊断报告")


def test_provider_metadata_extracts_usage(monkeypatch) -> None:
    """Provider metadata should expose trace-safe token usage and status."""

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return _fake_response(
                "带 usage 的回答",
                usage=SimpleNamespace(
                    prompt_tokens=12,
                    completion_tokens=6,
                    total_tokens=18,
                ),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(llm_service.openai, "OpenAI", FakeOpenAI)
    service = LLMService(provider="openai", api_key="fake-key", model="gpt-test")

    service.generate("请分析 P1001")
    metadata = service.provider_metadata()

    assert metadata["provider_status"] == "ok"
    assert metadata["token_usage"]["prompt_tokens"] == 12
    assert metadata["token_usage"]["completion_tokens"] == 6
    assert metadata["retry_count"] == 0
