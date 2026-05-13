"""Core business metric calculations used by the agent tools."""

from __future__ import annotations

from typing import Any

from app.db.database import get_connection


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


def analyze_channel_breakdown(
    product_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Analyze exposure, clicks, CTR, orders, and GMV by channel."""

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
