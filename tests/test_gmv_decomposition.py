"""Tests for GMV contribution decomposition."""

from app.agent.graph import run_agent
from app.db.init_db import initialize_database
from app.tools.metrics_tool import decompose_gmv_change


def test_decompose_gmv_change_returns_factor_effects() -> None:
    """GMV decomposition should expose all multiplicative drivers."""

    initialize_database()

    result = decompose_gmv_change(
        "P1001",
        "2026-04-01",
        "2026-04-30",
        "2026-03-01",
        "2026-03-31",
    )

    factors = {item["factor"] for item in result["factor_effects"]}

    assert result["formula"] == "GMV ≈ exposure × CTR × CVR × AOV"
    assert factors == {"exposure", "ctr", "cvr", "aov"}
    assert result["estimated_gmv"]["absolute_change"] < 0


def test_p1001_top_negative_factor_contains_ctr_or_cvr() -> None:
    """P1001 April vs March should point to traffic quality deterioration."""

    initialize_database()

    result = decompose_gmv_change(
        "P1001",
        "2026-04-01",
        "2026-04-30",
        "2026-03-01",
        "2026-03-31",
    )

    assert {"ctr", "cvr"}.intersection(result["top_negative_factors"])


def test_agent_result_contains_gmv_decomposition() -> None:
    """Agent output should include GMV decomposition in tools and report text."""

    initialize_database()

    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert "gmv_decomposition" in result["tool_results"]
    assert result["tool_results"]["gmv_decomposition"]["factor_effects"]
    assert "GMV 贡献度" in result["final_answer"]


def test_zero_baseline_safe() -> None:
    """Missing data should not raise division errors during decomposition."""

    initialize_database()

    result = decompose_gmv_change(
        "P9999",
        "2026-04-01",
        "2026-04-30",
        "2026-03-01",
        "2026-03-31",
    )

    assert result["estimated_gmv"]["baseline"] == 0
    assert result["estimated_gmv"]["percent_change"] is None
    assert result["factor_effects"]
