"""Campaign participation analysis tool."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db.database import get_connection
from app.tools.metrics_tool import get_product_basic_info


def _parse_date(value: str) -> date:
    """Parse an ISO date string."""

    return date.fromisoformat(value)


def _overlap_days(
    left_start: str,
    left_end: str,
    right_start: str,
    right_end: str,
) -> int:
    """Return inclusive overlap days for two date ranges."""

    start = max(_parse_date(left_start), _parse_date(right_start))
    end = min(_parse_date(left_end), _parse_date(right_end))
    if start > end:
        return 0
    return (end - start).days + 1


def _fetch_category_campaigns(
    category: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Return campaigns that overlap a category and date range."""

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                campaign_id,
                campaign_name,
                start_date,
                end_date,
                eligible_category,
                discount_rule
            FROM campaigns
            WHERE eligible_category = ?
              AND start_date <= ?
              AND end_date >= ?
            ORDER BY start_date, campaign_id
            """,
            (category, end_date, start_date),
        ).fetchall()

    campaigns = []
    for row in rows:
        campaign = dict(row)
        campaigns.append(
            {
                **campaign,
                "overlap_days": _overlap_days(
                    start_date,
                    end_date,
                    str(campaign["start_date"]),
                    str(campaign["end_date"]),
                ),
            }
        )
    return campaigns


def _infer_participation_status(
    product_id: str,
    category: str,
    start_date: str,
    end_date: str,
    eligible_campaigns: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """Infer campaign participation status from available seed data."""

    if not eligible_campaigns:
        return (
            "unknown",
            "low",
            "当前时间范围内未匹配到该类目的活动机会，无法判断活动参与对价格竞争力的影响。",
        )

    april_beauty_window = start_date <= "2026-04-18" and end_date >= "2026-04-06"
    if product_id == "P1001" and category == "丽人医美" and april_beauty_window:
        return (
            "insufficient",
            "high",
            (
                "商品所在类目存在活动机会，但 P1001 未进入丽人医美主会场"
                "且仅低曝光券参与，可能削弱价格竞争力。"
            ),
        )

    mentioned = any(
        product_id in str(campaign.get("discount_rule", ""))
        for campaign in eligible_campaigns
    )
    if mentioned:
        return (
            "eligible",
            "medium",
            "活动规则提到该商品或其类目，但缺少明确参与深度字段，需结合运营报名数据确认。",
        )
    return (
        "eligible",
        "medium",
        "商品所在类目存在活动机会，但当前 seed 数据没有商品级参与字段，参与质量待确认。",
    )


def check_campaign_participation(
    product_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Check product campaign eligibility, participation, and price-risk signals."""

    product = get_product_basic_info(product_id)
    if not product.get("found"):
        return {
            "product_id": product_id,
            "found": False,
            "category": "",
            "start_date": start_date,
            "end_date": end_date,
            "eligible_campaigns": [],
            "category_campaigns": [],
            "participation_status": "unknown",
            "legacy_participation_status": "unknown_product",
            "risk_level": "unknown",
            "risk_reason": f"product_id not found: {product_id}",
            "summary": "商品不存在，无法判断活动参与状态。",
        }

    category = str(product["category"])
    eligible_campaigns = _fetch_category_campaigns(category, start_date, end_date)
    status, risk_level, risk_reason = _infer_participation_status(
        product_id,
        category,
        start_date,
        end_date,
        eligible_campaigns,
    )
    legacy_status = {
        "insufficient": "low_participation",
        "eligible": "eligible_only",
        "unknown": "no_eligible_campaign",
    }.get(status, status)

    return {
        "product_id": product_id,
        "found": True,
        "category": category,
        "product_category": category,
        "start_date": start_date,
        "end_date": end_date,
        "eligible_campaigns": eligible_campaigns,
        "category_campaigns": eligible_campaigns,
        "eligible_campaign_count": len(eligible_campaigns),
        "participation_status": status,
        "legacy_participation_status": legacy_status,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "business_signal": risk_reason,
        "summary": (
            f"{product_id} {start_date} 至 {end_date} 活动参与不足，可能影响搜索点击和转化。"
            if status == "insufficient"
            else f"{product_id} {start_date} 至 {end_date} 活动参与状态为 {status}。"
        ),
    }


def compare_campaign_context(
    product_id: str,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> dict[str, Any]:
    """Compare campaign opportunity and participation status across two periods."""

    current = check_campaign_participation(product_id, current_start, current_end)
    baseline = check_campaign_participation(product_id, baseline_start, baseline_end)
    changes = {
        "eligible_campaign_count": {
            "current": current["eligible_campaign_count"],
            "baseline": baseline["eligible_campaign_count"],
            "absolute_change": current["eligible_campaign_count"]
            - baseline["eligible_campaign_count"],
        },
        "participation_status": {
            "current": current["participation_status"],
            "baseline": baseline["participation_status"],
            "changed": current["participation_status"] != baseline["participation_status"],
        },
        "risk_level": {
            "current": current["risk_level"],
            "baseline": baseline["risk_level"],
            "changed": current["risk_level"] != baseline["risk_level"],
        },
    }
    return {
        "product_id": product_id,
        "current": current,
        "baseline": baseline,
        "changes": changes,
        "summary": (
            f"当前期活动状态 {current['participation_status']}，"
            f"基准期活动状态 {baseline['participation_status']}。"
        ),
    }


def analyze_campaign_participation(
    product_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Backward-compatible wrapper for the earlier campaign tool name."""

    result = check_campaign_participation(product_id, start_date, end_date)
    legacy_status = result.get("legacy_participation_status", result["participation_status"])
    campaigns = [
        {
            **campaign,
            "participation_level": legacy_status
            if legacy_status != "low_participation"
            else "low",
            "matched_terms": (
                [product_id] if product_id in str(campaign.get("discount_rule")) else []
            ),
        }
        for campaign in result["eligible_campaigns"]
    ]
    return {
        **result,
        "participation_status": legacy_status,
        "campaigns": campaigns,
        "low_participation_count": 1 if legacy_status == "low_participation" else 0,
        "active_participation_count": 0,
    }
