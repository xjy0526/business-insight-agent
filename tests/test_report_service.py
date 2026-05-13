"""Tests for structured diagnosis report generation."""

from app.agent.graph import run_agent
from app.db.init_db import initialize_database


def test_multi_product_report_mentions_peer_product() -> None:
    """A comparison query should keep peer-product context in the report."""

    initialize_database()
    result = run_agent("请对比 P1001 和 P1002 四月 GMV 表现，判断 P1001 是否异常")

    assert result["related_entity_ids"] == ["P1002"]
    assert "peer_period_comparisons" in result["tool_results"]
    assert "P1002" in result["final_answer"]
