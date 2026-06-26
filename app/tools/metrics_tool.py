"""Core business metric calculations used by the agent tools."""

from __future__ import annotations

from typing import Any

from app.db.database import get_connection
from app.services.metrics_gateway import MetricsGateway


def _external_metric(metric_name: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Return external metric payload when a production backend is configured."""

    return MetricsGateway().fetch_metric(metric_name, params)


def _safe_divide(numerator: float, denominator: float) -> float:
    """Return a rounded division result and avoid ZeroDivisionError."""

    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _percent_change(current_value: float, baseline_value: float) -> float | None:
    """Return percent change, or None when the baseline is zero."""

    if baseline_value == 0:
        return None
    return round((current_value - baseline_value) / baseline_value, 6)


def get_product_basic_info(product_id: str) -> dict[str, Any]:
    """Return product name, category, brand, and price."""

    external = _external_metric("get_product_basic_info", {"product_id": product_id})
    if external is not None:
        return external

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT product_id, product_name, category, brand, price
            FROM products
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()

    if row is None:
        return {"product_id": product_id, "found": False}

    result = dict(row)
    result["found"] = True
    return result


def calculate_gmv(product_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Calculate GMV, order count, and sold quantity for a product."""

    external = _external_metric(
        "calculate_gmv",
        {"product_id": product_id, "start_date": start_date, "end_date": end_date},
    )
    if external is not None:
        return external

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(payment_amount), 0) AS gmv,
                COUNT(*) AS order_count,
                COALESCE(SUM(quantity), 0) AS sales_quantity
            FROM orders
            WHERE product_id = ?
              AND order_date BETWEEN ? AND ?
            """,
            (product_id, start_date, end_date),
        ).fetchone()

    return {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date,
        "gmv": round(float(row["gmv"]), 2),
        "order_count": int(row["order_count"]),
        "sales_quantity": int(row["sales_quantity"]),
    }


def calculate_traffic_metrics(
    product_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Calculate exposure, clicks, CTR, add-to-cart, orders, and CVR."""

    external = _external_metric(
        "calculate_traffic_metrics",
        {"product_id": product_id, "start_date": start_date, "end_date": end_date},
    )
    if external is not None:
        return external

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(exposure), 0) AS exposure,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(add_to_cart), 0) AS add_to_cart,
                COALESCE(SUM(orders), 0) AS order_count
            FROM traffic
            WHERE product_id = ?
              AND date BETWEEN ? AND ?
            """,
            (product_id, start_date, end_date),
        ).fetchone()

    exposure = int(row["exposure"])
    clicks = int(row["clicks"])
    order_count = int(row["order_count"])

    return {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date,
        "exposure": exposure,
        "clicks": clicks,
        "ctr": _safe_divide(clicks, exposure),
        "add_to_cart": int(row["add_to_cart"]),
        "order_count": order_count,
        "cvr": _safe_divide(order_count, clicks),
    }


def calculate_refund_rate(
    product_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Calculate refund order count and refund rate."""

    external = _external_metric(
        "calculate_refund_rate",
        {"product_id": product_id, "start_date": start_date, "end_date": end_date},
    )
    if external is not None:
        return external

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS order_count,
                COALESCE(SUM(refund_flag), 0) AS refund_order_count
            FROM orders
            WHERE product_id = ?
              AND order_date BETWEEN ? AND ?
            """,
            (product_id, start_date, end_date),
        ).fetchone()

    order_count = int(row["order_count"])
    refund_order_count = int(row["refund_order_count"])

    return {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date,
        "order_count": order_count,
        "refund_order_count": refund_order_count,
        "refund_rate": _safe_divide(refund_order_count, order_count),
    }


def calculate_aov(product_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Calculate average order value for a product."""

    external = _external_metric(
        "calculate_aov",
        {"product_id": product_id, "start_date": start_date, "end_date": end_date},
    )
    if external is not None:
        return external

    gmv_result = calculate_gmv(product_id, start_date, end_date)
    aov = _safe_divide(gmv_result["gmv"], gmv_result["order_count"])

    return {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date,
        "gmv": gmv_result["gmv"],
        "order_count": gmv_result["order_count"],
        "aov": round(aov, 2),
    }


def _period_summary(product_id: str, start_date: str, end_date: str) -> dict[str, float]:
    """Return the compact metric set used for period comparison."""

    gmv = calculate_gmv(product_id, start_date, end_date)
    traffic = calculate_traffic_metrics(product_id, start_date, end_date)
    refund = calculate_refund_rate(product_id, start_date, end_date)
    aov = calculate_aov(product_id, start_date, end_date)

    return {
        "gmv": gmv["gmv"],
        "ctr": traffic["ctr"],
        "cvr": traffic["cvr"],
        "aov": aov["aov"],
        "refund_rate": refund["refund_rate"],
    }


def compare_periods(
    product_id: str,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> dict[str, Any]:
    """Compare GMV, CTR, CVR, AOV, and refund rate across two periods."""

    external = _external_metric(
        "compare_periods",
        {
            "product_id": product_id,
            "current_start": current_start,
            "current_end": current_end,
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
        },
    )
    if external is not None:
        return external

    current = _period_summary(product_id, current_start, current_end)
    baseline = _period_summary(product_id, baseline_start, baseline_end)

    changes = {}
    for metric_name, current_value in current.items():
        baseline_value = baseline[metric_name]
        changes[metric_name] = {
            "current": current_value,
            "baseline": baseline_value,
            "absolute_change": round(current_value - baseline_value, 6),
            "percent_change": _percent_change(current_value, baseline_value),
        }

    return {
        "product_id": product_id,
        "current_period": {
            "start_date": current_start,
            "end_date": current_end,
            "metrics": current,
        },
        "baseline_period": {
            "start_date": baseline_start,
            "end_date": baseline_end,
            "metrics": baseline,
        },
        "changes": changes,
    }


GMV_DRIVER_NAMES = ("exposure", "ctr", "cvr", "aov")
GMV_DRIVER_LABELS = {
    "exposure": "曝光量",
    "ctr": "点击率 CTR",
    "cvr": "转化率 CVR",
    "aov": "客单价 AOV",
}


def _gmv_driver_summary(product_id: str, start_date: str, end_date: str) -> dict[str, float]:
    """Return multiplicative GMV drivers for contribution decomposition."""

    traffic = calculate_traffic_metrics(product_id, start_date, end_date)
    aov = calculate_aov(product_id, start_date, end_date)
    return {
        "exposure": float(traffic["exposure"]),
        "ctr": float(traffic["ctr"]),
        "cvr": float(traffic["cvr"]),
        "aov": float(aov["aov"]),
    }


def _estimated_gmv(drivers: dict[str, float]) -> float:
    """Estimate GMV as exposure * CTR * CVR * AOV."""

    return round(
        drivers["exposure"] * drivers["ctr"] * drivers["cvr"] * drivers["aov"],
        6,
    )


def _factor_interpretation(
    factor_name: str,
    effect: float,
    normalized_abs_share: float,
) -> str:
    """Return a compact Chinese explanation for one GMV driver effect."""

    if effect < 0:
        if normalized_abs_share >= 0.35:
            return f"{factor_name}下降对 GMV 下滑贡献较高"
        return f"{factor_name}变化对 GMV 形成负向影响"
    if effect > 0:
        return f"{factor_name}变化对 GMV 形成正向拉动"
    return f"{factor_name}对本期 GMV 变化影响不明显"


def _build_gmv_decomposition_summary(top_factors: list[str], actual_delta: float) -> str:
    """Build a human-readable summary for the decomposition result."""

    if actual_delta == 0:
        return "GMV 当前期与基准期基本持平，各因素贡献需结合更细粒度数据继续观察。"
    if not top_factors:
        direction = "下滑" if actual_delta < 0 else "增长"
        return f"GMV {direction}未发现单一显著负向驱动，需结合渠道、活动和评价证据进一步确认。"

    label_text = "、".join(GMV_DRIVER_LABELS.get(factor, factor) for factor in top_factors[:2])
    if actual_delta < 0:
        return f"GMV 下滑主要受{label_text}下降影响，退款率是额外售后风险信号。"
    return f"GMV 增长主要由{label_text}改善带动，仍需持续监控退款率和评价风险。"


def _single_factor_effects(
    baseline_drivers: dict[str, float],
    current_drivers: dict[str, float],
    estimated_baseline: float,
) -> dict[str, float]:
    """Calculate single-factor replacement effects for all GMV drivers."""

    raw_effects: dict[str, float] = {}
    for driver in GMV_DRIVER_NAMES:
        replaced_drivers = baseline_drivers.copy()
        replaced_drivers[driver] = current_drivers[driver]
        raw_effects[driver] = _estimated_gmv(replaced_drivers) - estimated_baseline
    return raw_effects


def _build_factor_effects(
    baseline_drivers: dict[str, float],
    current_drivers: dict[str, float],
    raw_effects: dict[str, float],
    estimated_delta: float,
) -> list[dict[str, Any]]:
    """Build display-ready factor effect records."""

    total_abs_effect = sum(abs(effect) for effect in raw_effects.values())
    factor_effects: list[dict[str, Any]] = []
    for driver in GMV_DRIVER_NAMES:
        effect = round(raw_effects[driver], 2)
        normalized_abs_share = (
            round(abs(raw_effects[driver]) / total_abs_effect, 6)
            if total_abs_effect
            else 0.0
        )
        factor_name = GMV_DRIVER_LABELS[driver]
        factor_effects.append(
            {
                "factor": driver,
                "factor_name": factor_name,
                "baseline": baseline_drivers[driver],
                "current": current_drivers[driver],
                "absolute_change": round(current_drivers[driver] - baseline_drivers[driver], 6),
                "percent_change": _percent_change(
                    current_drivers[driver],
                    baseline_drivers[driver],
                ),
                "effect": effect,
                "effect_direction": (
                    "negative" if effect < 0 else "positive" if effect > 0 else "neutral"
                ),
                "contribution_share": (
                    round(raw_effects[driver] / estimated_delta, 6)
                    if estimated_delta
                    else None
                ),
                "normalized_abs_share": normalized_abs_share,
                "interpretation": _factor_interpretation(
                    factor_name,
                    effect,
                    normalized_abs_share,
                ),
            }
        )
    return factor_effects


def _top_negative_factors(factor_effects: list[dict[str, Any]]) -> list[str]:
    """Return negative drivers ordered by absolute normalized share."""

    return [
        item["factor"]
        for item in sorted(
            (item for item in factor_effects if item["effect"] < 0),
            key=lambda item: item["normalized_abs_share"],
            reverse=True,
        )
    ]


def _driver_contribution_rows(factor_effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return backward-compatible driver contribution rows."""

    return [
        {
            "driver": item["factor"],
            "baseline": item["baseline"],
            "current": item["current"],
            "absolute_change": item["absolute_change"],
            "percent_change": item["percent_change"],
            "estimated_gmv_contribution": item["effect"],
        }
        for item in factor_effects
    ]


def _period_payload(
    start_date: str,
    end_date: str,
    drivers: dict[str, float],
    actual_gmv: float,
    estimated_gmv: float,
) -> dict[str, Any]:
    """Build a period payload for GMV decomposition output."""

    return {
        "start_date": start_date,
        "end_date": end_date,
        "metrics": drivers,
        "actual_gmv": actual_gmv,
        "estimated_gmv": round(estimated_gmv, 2),
    }


def decompose_gmv_change(
    product_id: str,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> dict[str, Any]:
    """Decompose GMV movement into exposure, CTR, CVR, and AOV contributions.

    GMV is approximated as exposure * CTR * CVR * AOV. Each factor effect is
    calculated by replacing one current-period factor while keeping other
    factors at baseline values. This is intentionally simple and explainable
    for business diagnostics rather than a strict econometric attribution.
    """

    external = _external_metric(
        "decompose_gmv_change",
        {
            "product_id": product_id,
            "current_start": current_start,
            "current_end": current_end,
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
        },
    )
    if external is not None:
        return external

    baseline_drivers = _gmv_driver_summary(product_id, baseline_start, baseline_end)
    current_drivers = _gmv_driver_summary(product_id, current_start, current_end)
    actual_current = calculate_gmv(product_id, current_start, current_end)["gmv"]
    actual_baseline = calculate_gmv(product_id, baseline_start, baseline_end)["gmv"]
    estimated_current = _estimated_gmv(current_drivers)
    estimated_baseline = _estimated_gmv(baseline_drivers)
    estimated_delta = round(estimated_current - estimated_baseline, 2)
    actual_delta = round(actual_current - actual_baseline, 2)
    raw_effects = _single_factor_effects(
        baseline_drivers,
        current_drivers,
        estimated_baseline,
    )
    factor_effects = _build_factor_effects(
        baseline_drivers,
        current_drivers,
        raw_effects,
        estimated_delta,
    )
    top_negative_factors = _top_negative_factors(factor_effects)

    return {
        "product_id": product_id,
        "formula": "GMV ≈ exposure × CTR × CVR × AOV",
        "method": "single_factor_replacement",
        "approximation_note": (
            "这是基于 traffic 与 orders 聚合口径的近似拆解；"
            "estimated_gmv 与真实订单 GMV 可能存在 residual 差异。"
        ),
        "current_period": _period_payload(
            current_start,
            current_end,
            current_drivers,
            actual_current,
            estimated_current,
        ),
        "baseline_period": _period_payload(
            baseline_start,
            baseline_end,
            baseline_drivers,
            actual_baseline,
            estimated_baseline,
        ),
        "estimated_gmv": {
            "current": round(estimated_current, 2),
            "baseline": round(estimated_baseline, 2),
            "absolute_change": estimated_delta,
            "percent_change": _percent_change(estimated_current, estimated_baseline),
        },
        "actual_gmv": {
            "current": actual_current,
            "baseline": actual_baseline,
            "absolute_change": actual_delta,
            "percent_change": _percent_change(actual_current, actual_baseline),
        },
        "factor_effects": factor_effects,
        "top_negative_factors": top_negative_factors,
        "summary": _build_gmv_decomposition_summary(top_negative_factors, actual_delta),
        # Backward-compatible fields for existing API/tests/docs.
        "estimated_delta": estimated_delta,
        "actual_delta": actual_delta,
        "residual": round(actual_delta - estimated_delta, 2),
        "driver_contributions": _driver_contribution_rows(factor_effects),
    }


def decompose_gmv_contribution(
    product_id: str,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> dict[str, Any]:
    """Backward-compatible alias for GMV contribution decomposition."""

    return decompose_gmv_change(
        product_id,
        current_start,
        current_end,
        baseline_start,
        baseline_end,
    )


def analyze_channel_breakdown(
    product_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Analyze exposure, clicks, CTR, orders, and GMV by channel."""

    external = _external_metric(
        "analyze_channel_breakdown",
        {"product_id": product_id, "start_date": start_date, "end_date": end_date},
    )
    if external is not None:
        return external

    with get_connection() as connection:
        traffic_rows = connection.execute(
            """
            SELECT
                channel,
                COALESCE(SUM(exposure), 0) AS exposure,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(add_to_cart), 0) AS add_to_cart,
                COALESCE(SUM(orders), 0) AS traffic_order_count
            FROM traffic
            WHERE product_id = ?
              AND date BETWEEN ? AND ?
            GROUP BY channel
            ORDER BY channel
            """,
            (product_id, start_date, end_date),
        ).fetchall()
        order_rows = connection.execute(
            """
            SELECT
                channel,
                COUNT(*) AS order_count,
                COALESCE(SUM(payment_amount), 0) AS gmv
            FROM orders
            WHERE product_id = ?
              AND order_date BETWEEN ? AND ?
            GROUP BY channel
            """,
            (product_id, start_date, end_date),
        ).fetchall()

    orders_by_channel = {
        row["channel"]: {
            "order_count": int(row["order_count"]),
            "gmv": round(float(row["gmv"]), 2),
        }
        for row in order_rows
    }

    channels = []
    for row in traffic_rows:
        channel = row["channel"]
        exposure = int(row["exposure"])
        clicks = int(row["clicks"])
        order_stats = orders_by_channel.get(channel, {"order_count": 0, "gmv": 0.0})

        channels.append(
            {
                "channel": channel,
                "exposure": exposure,
                "clicks": clicks,
                "ctr": _safe_divide(clicks, exposure),
                "add_to_cart": int(row["add_to_cart"]),
                "traffic_order_count": int(row["traffic_order_count"]),
                "order_count": order_stats["order_count"],
                "gmv": order_stats["gmv"],
            }
        )

    return {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date,
        "channels": channels,
    }
