"""Tests for review and campaign business tools."""

import pytest
from app.db.init_db import initialize_database
from app.tools.campaign_tool import analyze_campaign_participation
from app.tools.review_tool import analyze_review_topics


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    """Ensure tool tests run against fresh seed data."""

    initialize_database()


def test_review_tool_finds_p1001_negative_topics() -> None:
    """P1001 April reviews should surface logistics, battery, and comfort themes."""

    result = analyze_review_topics("P1001", "2026-04-01", "2026-04-30")
    labels = {topic["label"] for topic in result["topics"]}

    assert result["review_count"] > 0
    assert result["negative_review_count"] > 0
    assert {"物流履约", "续航体验", "佩戴舒适度"}.issubset(labels)


def test_campaign_tool_marks_p1001_low_participation() -> None:
    """P1001 should be eligible for the April audio campaign but low participation."""

    result = analyze_campaign_participation("P1001", "2026-04-01", "2026-04-30")

    assert result["found"] is True
    assert result["eligible_campaign_count"] == 1
    assert result["participation_status"] == "low_participation"
    assert result["low_participation_count"] == 1
