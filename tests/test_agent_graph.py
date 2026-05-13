"""End-to-end tests for the agent state machine."""

from app.agent.graph import run_agent
from app.db.init_db import initialize_database


def test_run_agent_generates_business_diagnosis_report() -> None:
    """P1001 GMV question should produce a structured diagnosis."""

    initialize_database()

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert result["trace_id"]
    assert result["tool_results"]
    assert result["retrieved_docs"]

    final_answer = result["final_answer"]
    assert "GMV" in final_answer
    assert "退款率" in final_answer
    assert "点击率" in final_answer
    assert "优化建议" in final_answer


def test_run_agent_unknown_product_uses_clear_fallback() -> None:
    """Unknown product IDs should not be reported as normal zero metrics."""

    initialize_database()

    result = run_agent("商品 P9999 最近 GMV 为什么下降？")

    assert result["trace_id"]
    assert result["errors"]
    assert "product_id not found: P9999" in result["final_answer"]
    assert "数据分析失败原因" in result["final_answer"]
