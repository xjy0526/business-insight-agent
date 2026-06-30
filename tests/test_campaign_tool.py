"""Tests for the Campaign Tool."""

import pytest
from app.db.init_db import initialize_database
from app.tools.campaign_tool import check_campaign_participation, compare_campaign_context


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    """Ensure campaign tests run against fresh seed data."""

    initialize_database()


def test_check_campaign_participation_p1001_april() -> None:
    """P1001 should show insufficient participation in the April beauty campaign."""

    result = check_campaign_participation("P1001", "2026-04-01", "2026-04-30")

    assert result["participation_status"] == "insufficient" or result["risk_level"] == "high"
    assert result["eligible_campaigns"] or result["risk_reason"]
    assert "价格竞争力" in result["risk_reason"]


def test_compare_campaign_context() -> None:
    """Campaign context comparison should expose current and baseline status."""

    result = compare_campaign_context(
        "P1001",
        "2026-04-01",
        "2026-04-30",
        "2026-03-01",
        "2026-03-31",
    )

    assert {"current", "baseline", "changes"}.issubset(result)
    assert result["current"]["risk_level"] == "high"
    assert result["changes"]["participation_status"]["changed"] is True


def test_campaign_tool_unknown_product_safe() -> None:
    """Unknown products should return a structured not-found result."""

    result = check_campaign_participation("P9999", "2026-04-01", "2026-04-30")

    assert result["found"] is False
    assert result["eligible_campaigns"] == []
    assert result["participation_status"] == "unknown"
