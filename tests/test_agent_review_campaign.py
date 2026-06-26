"""Agent integration tests for Review Tool and Campaign Tool."""

import pytest
from app.agent.graph import run_agent
from app.db.init_db import initialize_database


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    """Ensure agent integration tests run against fresh seed data."""

    initialize_database()


def test_gmv_query_contains_review_and_campaign_tools() -> None:
    """GMV diagnosis should include deterministic review and campaign evidence."""

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert "review_analysis" in result["tool_results"]
    assert "review_period_comparison" in result["tool_results"]
    assert "campaign_participation" in result["tool_results"]
    assert "campaign_context_comparison" in result["tool_results"]


def test_review_query_final_answer_contains_top_topics() -> None:
    """Review questions should surface the top negative review topics."""

    result = run_agent("商品 P1001 差评集中在哪些问题？")

    assert "review_analysis" in result["tool_results"]
    expected_topics = ("续航不达预期", "物流慢", "佩戴不舒服")
    assert any(topic in result["final_answer"] for topic in expected_topics)


def test_campaign_query_final_answer_contains_campaign_risk() -> None:
    """Campaign questions should mention insufficient participation or price risk."""

    result = run_agent("P1001 4 月活动参与是否影响 GMV？")

    assert "campaign_participation" in result["tool_results"]
    assert "活动参与不足" in result["final_answer"] or "价格竞争力" in result["final_answer"]
