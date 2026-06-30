"""Tests for the Review Tool."""

import pytest
from app.db.init_db import initialize_database
from app.tools.review_tool import analyze_review_topics, compare_review_periods


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    """Ensure review tests run against fresh seed data."""

    initialize_database()


def test_analyze_review_topics_p1001_april() -> None:
    """P1001 April reviews should expose deterministic negative topics."""

    result = analyze_review_topics("P1001", "2026-04-01", "2026-04-30")

    assert result["negative_review_count"] > 0
    assert {"效果不明显", "等待时间长", "服务体验不舒服"}.intersection(
        result["top_topics"]
    )
    assert result["topic_distribution"]
    assert result["sample_negative_reviews"]


def test_compare_review_periods() -> None:
    """Review comparison should include current, baseline, and change records."""

    result = compare_review_periods(
        "P1001",
        "2026-04-01",
        "2026-04-30",
        "2026-03-01",
        "2026-03-31",
    )

    assert {"current", "baseline", "changes"}.issubset(result)
    assert result["current"]["negative_review_rate"] >= result["baseline"][
        "negative_review_rate"
    ]
    assert result["current"]["top_topics"]


def test_review_tool_empty_safe() -> None:
    """Missing products or empty date windows should return zero evidence safely."""

    result = analyze_review_topics("P9999", "2026-01-01", "2026-01-31")

    assert result["review_count"] == 0
    assert result["negative_review_count"] == 0
    assert result["negative_review_rate"] == 0.0
    assert result["top_topics"] == []
