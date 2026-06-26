"""Integration tests for reflection checker node output."""

from app.agent.graph import run_agent
from app.db.init_db import initialize_database


def test_reflection_checker_node_outputs_claim_level_result() -> None:
    """A normal GMV query should produce claim-level reflection details."""

    initialize_database()

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")
    reflection_result = result["reflection_result"]

    assert "claim_checks" in reflection_result
    assert "overall_confidence" in reflection_result
    assert "structure_check" in reflection_result
    assert any(check["supported"] for check in reflection_result["claim_checks"])
    assert "overall_confidence=" in result["final_answer"]
