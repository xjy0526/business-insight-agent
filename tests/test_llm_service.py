"""Tests for the LLM service mock behavior."""

from app.agent.prompts import INTENT_ROUTER_PROMPT
from app.services.llm_service import LLMService


def test_mock_generate_json_returns_dict() -> None:
    """Mock JSON generation should return a dictionary."""

    service = LLMService(provider="mock")
    result = service.generate_json(INTENT_ROUTER_PROMPT.format(query="P1001 最近 GMV 为什么下降？"))

    assert isinstance(result, dict)
    assert "intent" in result


def test_p1001_gmv_query_is_business_diagnosis() -> None:
    """P1001 GMV questions should route to business diagnosis in mock mode."""

    service = LLMService(provider="mock")
    result = service.generate_json(
        INTENT_ROUTER_PROMPT.format(query="商品 P1001 最近 GMV 为什么下降？")
    )

    assert result["intent"] == "business_diagnosis"
    assert result["entity_id"] == "P1001"
    assert result["metric"] == "gmv"


def test_missing_api_key_falls_back_to_mock_without_error() -> None:
    """Reserved real providers should not fail locally when no API key exists."""

    service = LLMService(provider="openai", api_key=None)
    result = service.generate_json(INTENT_ROUTER_PROMPT.format(query="P1001 最近 GMV 为什么下降？"))

    assert service.uses_mock is True
    assert result["intent"] == "business_diagnosis"
