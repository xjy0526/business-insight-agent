"""Tests for business metric tools."""

import pytest
from app.db.init_db import initialize_database
from app.tools import sql_tool
from app.tools.metrics_tool import (
    analyze_channel_breakdown,
    calculate_gmv,
    calculate_refund_rate,
)
from app.tools.sql_tool import execute_readonly_query


@pytest.fixture(scope="module", autouse=True)
def seeded_database() -> None:
    """Ensure the default SQLite database is loaded from current CSV data."""

    initialize_database()


def test_p1001_april_gmv_decreases_from_march() -> None:
    """P1001 should show the designed April GMV drop."""

    march = calculate_gmv("P1001", "2026-03-01", "2026-03-31")
    april = calculate_gmv("P1001", "2026-04-01", "2026-04-30")

    assert april["gmv"] < march["gmv"]
    assert april["order_count"] < march["order_count"]


def test_p1001_april_refund_rate_increases_from_march() -> None:
    """P1001 should show the designed April refund-rate increase."""

    march = calculate_refund_rate("P1001", "2026-03-01", "2026-03-31")
    april = calculate_refund_rate("P1001", "2026-04-01", "2026-04-30")

    assert april["refund_rate"] > march["refund_rate"]


def test_p1001_april_search_ctr_decreases_from_march() -> None:
    """P1001 search channel should show the designed CTR decline in April."""

    march_channels = analyze_channel_breakdown("P1001", "2026-03-01", "2026-03-31")
    april_channels = analyze_channel_breakdown("P1001", "2026-04-01", "2026-04-30")

    march_search = next(row for row in march_channels["channels"] if row["channel"] == "search")
    april_search = next(row for row in april_channels["channels"] if row["channel"] == "search")

    assert april_search["ctr"] < march_search["ctr"]


def test_sql_tool_rejects_delete_statement() -> None:
    """The SQL helper should reject destructive statements."""

    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_readonly_query("DELETE FROM orders")


def test_sql_tool_rejects_multiple_statements() -> None:
    """The SQL helper should reject SELECT followed by a destructive statement."""

    with pytest.raises(ValueError, match="Only one SELECT statement is allowed"):
        execute_readonly_query("SELECT * FROM orders; DELETE FROM orders")


def test_sql_tool_returns_readonly_rows() -> None:
    """The SQL helper should return read-only query rows as dictionaries."""

    rows = execute_readonly_query("SELECT product_id, product_name FROM products LIMIT 1")

    assert rows
    assert set(rows[0]) == {"product_id", "product_name"}


def test_sql_tool_falls_back_when_sqlparse_is_unavailable(monkeypatch) -> None:
    """The SQL helper should still protect reads in minimal environments."""

    monkeypatch.setattr(sql_tool, "_sqlparse", None)

    rows = sql_tool.execute_readonly_query("SELECT product_id FROM products LIMIT 1")

    assert rows
    with pytest.raises(ValueError, match="Only one SELECT statement is allowed"):
        sql_tool.execute_readonly_query("SELECT * FROM products; SELECT * FROM orders")
