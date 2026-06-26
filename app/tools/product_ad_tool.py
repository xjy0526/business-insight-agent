"""Product-level advertising decision tools for local commerce demo data."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.db.database import get_connection

PRODUCT_AD_INTENTS = {
    "product_ad_strategy",
    "sku_mining",
    "sku_recall",
    "bid_recommendation",
    "poi_vs_product_ad_comparison",
}

GROWTH_WEIGHTS = {
    "cvr": 0.25,
    "gmv_share": 0.25,
    "pcvr": 0.20,
    "historical_roi": 0.15,
    "available_slots": 0.05,
    "rating": 0.05,
    "keyword_coverage": 0.05,
    "refund_rate": -0.15,
}


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Return a deterministic structured error payload."""

    return {"ok": False, "error": {"code": code, "message": message}, **extra}


def _ok(**payload: Any) -> dict[str, Any]:
    """Return a deterministic success payload."""

    return {"ok": True, **payload}


def _as_float(row: dict[str, Any], key: str) -> float:
    """Read a numeric SQLite/CSV value as float."""

    try:
        return float(row.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(row: dict[str, Any], key: str) -> int:
    """Read a numeric SQLite/CSV value as int."""

    try:
        return int(float(row.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def _fetch_product_rows(
    merchant_id: str | None = None,
    product_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch product-ad candidate rows from SQLite."""

    clauses: list[str] = []
    params: list[Any] = []
    if merchant_id:
        clauses.append("merchant_id = ?")
        params.append(merchant_id)
    if product_ids:
        placeholders = ", ".join("?" for _ in product_ids)
        clauses.append(f"product_id IN ({placeholders})")
        params.extend(product_ids)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM local_ad_sku_candidates
            {where_sql}
            ORDER BY merchant_id, product_id
            """,
            tuple(params),
        ).fetchall()
    return [dict(row) for row in rows]


def _fetch_product_row(product_id: str) -> dict[str, Any] | None:
    """Fetch one product-ad row by product_id."""

    rows = _fetch_product_rows(product_ids=[product_id])
    return rows[0] if rows else None


def _normalize_values(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    """Normalize one numeric field by product_id using min-max scaling."""

    if not rows:
        return {}
    values = [_as_float(row, key) for row in rows]
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return {str(row["product_id"]): 1.0 for row in rows}
    return {
        str(row["product_id"]): round(
            (_as_float(row, key) - min_value) / (max_value - min_value),
            6,
        )
        for row in rows
    }


def _score_product_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Calculate product_growth_score for each row."""

    normalized = {
        key: _normalize_values(rows, key)
        for key in GROWTH_WEIGHTS
    }
    scores: dict[str, float] = {}
    for row in rows:
        product_id = str(row["product_id"])
        score = sum(
            weight * normalized[key].get(product_id, 0.0)
            for key, weight in GROWTH_WEIGHTS.items()
        )
        scores[product_id] = round(max(score, 0.0), 6)
    return scores


def _risk_flags(row: dict[str, Any]) -> list[str]:
    """Build risk flags for one product candidate."""

    flags: list[str] = []
    if _as_float(row, "refund_rate") >= 0.08:
        flags.append("退款率偏高，需要关注履约和售后")
    elif _as_float(row, "refund_rate") >= 0.05:
        flags.append("退款率略高，建议先小流量验证")
    if _as_float(row, "rating") < 4.3:
        flags.append("评分偏低，可能影响广告承接效率")
    if _as_int(row, "available_slots") < 100:
        flags.append("可预约档期有限，需控制投放节奏")
    if _as_float(row, "historical_roi") < 3:
        flags.append("历史 ROI 低于常用目标阈值，出价应更谨慎")
    return flags


def _key_reasons(row: dict[str, Any], score: float) -> list[str]:
    """Build positive reasons for one product candidate."""

    reasons: list[str] = []
    if _as_float(row, "gmv_share") >= 0.25:
        reasons.append("GMV占比较高")
    if _as_float(row, "cvr") >= 0.16:
        reasons.append("CVR较高")
    if _as_float(row, "pcvr") >= 0.06:
        reasons.append("PCVR较高")
    if _as_float(row, "historical_roi") >= 3.5:
        reasons.append("历史ROI较好")
    if _as_float(row, "keyword_coverage") >= 0.7:
        reasons.append("关键词覆盖较好")
    if not reasons:
        reasons.append(f"综合增长分 {score:.3f}")
    return reasons


def _candidate_payload(row: dict[str, Any], rank: int, score: float) -> dict[str, Any]:
    """Format one product candidate for tool output."""

    return {
        "rank": rank,
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "merchant_id": row["merchant_id"],
        "poi_id": row["poi_id"],
        "category": row["category"],
        "service_type": row["service_type"],
        "price": _as_float(row, "price"),
        "cvr": _as_float(row, "cvr"),
        "gmv_share": _as_float(row, "gmv_share"),
        "pcvr": _as_float(row, "pcvr"),
        "historical_roi": _as_float(row, "historical_roi"),
        "margin_rate": _as_float(row, "margin_rate"),
        "available_slots": _as_int(row, "available_slots"),
        "rating": _as_float(row, "rating"),
        "refund_rate": _as_float(row, "refund_rate"),
        "keyword_coverage": _as_float(row, "keyword_coverage"),
        "is_current_bestseller": str(row.get("is_current_bestseller", "")).lower() == "true",
        "product_growth_score": round(score, 3),
        "key_reasons": _key_reasons(row, score),
        "risk_flags": _risk_flags(row),
    }


def mine_high_value_products(merchant_id: str, top_k: int = 5) -> dict[str, Any]:
    """Rank a merchant's products for product-level advertising."""

    try:
        rows = _fetch_product_rows(merchant_id=merchant_id)
        if not rows:
            return _error(
                "merchant_not_found",
                f"No local ad SKU candidates found for merchant_id={merchant_id}.",
                merchant_id=merchant_id,
                candidates=[],
            )

        scores = _score_product_rows(rows)
        ranked_rows = sorted(
            rows,
            key=lambda row: (
                scores[str(row["product_id"])],
                _as_float(row, "historical_roi"),
                _as_float(row, "gmv_share"),
            ),
            reverse=True,
        )
        candidates = [
            _candidate_payload(row, index, scores[str(row["product_id"])])
            for index, row in enumerate(ranked_rows[:top_k], start=1)
        ]
        return _ok(
            merchant_id=merchant_id,
            top_k=top_k,
            candidates=candidates,
            method=(
                "weighted scoring over CVR, GMV share, PCVR, ROI, slots, rating, "
                "keyword coverage and fulfillment risk"
            ),
        )
    except Exception as error:  # pragma: no cover - defensive guard for agent stability.
        return _error("tool_error", str(error), merchant_id=merchant_id, candidates=[])


def recommend_bid_range(product_id: str, target_roi: float = 3.0) -> dict[str, Any]:
    """Estimate acceptable CPC range under a target ROI guardrail."""

    try:
        row = _fetch_product_row(product_id)
        if row is None:
            return _error(
                "product_not_found",
                f"No local ad SKU candidate found for product_id={product_id}.",
                product_id=product_id,
            )

        price = _as_float(row, "price")
        pcvr = _as_float(row, "pcvr")
        margin_rate = _as_float(row, "margin_rate")
        refund_rate = _as_float(row, "refund_rate")
        historical_roi = _as_float(row, "historical_roi")
        safe_target_roi = target_roi if target_roi > 0 else 3.0

        expected_revenue_per_click = pcvr * price
        expected_profit_per_click = expected_revenue_per_click * margin_rate
        max_cpc_by_revenue_roi = expected_revenue_per_click / safe_target_roi
        max_cpc_by_profit_roi = expected_profit_per_click / safe_target_roi
        lower = max_cpc_by_profit_roi * 0.6
        upper = min(max_cpc_by_revenue_roi, max_cpc_by_profit_roi * 1.3)
        risk_flags = _risk_flags(row)
        if refund_rate >= 0.07:
            upper *= 0.85
            if not any("退款率" in flag for flag in risk_flags):
                risk_flags.append("退款率偏高，上限出价已做风险折扣")

        if historical_roi < safe_target_roi or refund_rate >= 0.10:
            bid_strategy = "conservative"
        elif historical_roi >= safe_target_roi * 1.25 and refund_rate < 0.04:
            bid_strategy = "aggressive"
        else:
            bid_strategy = "balanced"

        return _ok(
            product_id=product_id,
            product_name=row["product_name"],
            merchant_id=row["merchant_id"],
            poi_id=row["poi_id"],
            pcvr=round(pcvr, 4),
            price=round(price, 2),
            target_roi=round(safe_target_roi, 2),
            expected_revenue_per_click=round(expected_revenue_per_click, 2),
            expected_profit_per_click=round(expected_profit_per_click, 2),
            max_cpc_by_revenue_roi=round(max_cpc_by_revenue_roi, 2),
            max_cpc_by_profit_roi=round(max_cpc_by_profit_roi, 2),
            recommended_cpc_range=[round(lower, 2), round(max(upper, lower), 2)],
            bid_strategy=bid_strategy,
            risk_flags=risk_flags,
            explanation=(
                "CPC upper bound is constrained by target ROI, expected profit per click "
                "and refund-risk discount when applicable."
            ),
        )
    except Exception as error:  # pragma: no cover
        return _error("tool_error", str(error), product_id=product_id)


def _term_overlap_score(query: str, row: dict[str, Any]) -> float:
    """Return a simple deterministic overlap score for fallback recall."""

    normalized_query = query.lower().replace(" ", "")
    row_query = str(row.get("query", "")).lower().replace(" ", "")
    product_name = str(row.get("product_name", "")).lower().replace(" ", "")
    matched_terms = [
        term.lower().replace(" ", "")
        for term in str(row.get("matched_terms", "")).split("|")
        if term.strip()
    ]
    if not normalized_query:
        return 0.0
    score = 0.0
    if normalized_query == row_query:
        score += 1.0
    elif normalized_query in row_query or row_query in normalized_query:
        score += 0.65
    if normalized_query in product_name:
        score += 0.45
    score += 0.18 * sum(
        1
        for term in matched_terms
        if term and (term in normalized_query or normalized_query in term)
    )
    return round(score, 6)


def recall_query_to_sku(query: str, top_k: int = 5) -> dict[str, Any]:
    """Run deterministic multi-path Query-SKU recall from demo rows."""

    try:
        cleaned_query = query.strip()
        if not cleaned_query:
            return _error("missing_query", "query is required.", query=query, results=[])

        with get_connection() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM query_sku_recall
                    ORDER BY query, recall_score DESC, product_id
                    """
                ).fetchall()
            ]

        exact_rows = [
            row
            for row in rows
            if str(row["query"]).lower().replace(" ", "")
            == cleaned_query.lower().replace(" ", "")
        ]
        candidate_rows = exact_rows
        if not candidate_rows:
            scored_rows = [
                (row, _term_overlap_score(cleaned_query, row))
                for row in rows
            ]
            candidate_rows = [
                row
                for row, score in sorted(
                    scored_rows,
                    key=lambda item: (item[1], _as_float(item[0], "recall_score")),
                    reverse=True,
                )
                if score > 0
            ]

        results = [
            {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "merchant_id": row["merchant_id"],
                "poi_id": row["poi_id"],
                "recall_path": row["recall_path"],
                "recall_score": _as_float(row, "recall_score"),
                "matched_terms": row["matched_terms"],
                "query_intent": row["query_intent"],
            }
            for row in sorted(
                candidate_rows,
                key=lambda item: _as_float(item, "recall_score"),
                reverse=True,
            )[:top_k]
        ]
        paths = []
        for result in results:
            recall_path = result["recall_path"]
            if recall_path not in paths:
                paths.append(recall_path)
        return _ok(
            query=cleaned_query,
            top_k=top_k,
            recall_paths_used=paths,
            results=results,
            method="exact query rows first, then token overlap fallback over demo recall rows",
        )
    except Exception as error:  # pragma: no cover
        return _error("tool_error", str(error), query=query, results=[])


def _recall_score_by_product(recall_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the highest recall row per product."""

    best: dict[str, dict[str, Any]] = {}
    for result in recall_result.get("results", []):
        product_id = str(result.get("product_id", ""))
        if not product_id:
            continue
        previous = best.get(product_id)
        if previous is None or result.get("recall_score", 0) > previous.get("recall_score", 0):
            best[product_id] = result
    return best


def rank_ad_candidates(
    query: str | None = None,
    merchant_id: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Fuse product growth score and optional Query-SKU recall score."""

    try:
        recall_result = recall_query_to_sku(query, top_k=top_k * 3) if query else {}
        recall_by_product = _recall_score_by_product(recall_result)
        product_ids = list(recall_by_product) if query and not merchant_id else None
        rows = _fetch_product_rows(merchant_id=merchant_id, product_ids=product_ids)
        if query and merchant_id:
            recall_product_ids = set(recall_by_product)
            rows = [
                row
                for row in rows
                if row["product_id"] in recall_product_ids
                or str(row["merchant_id"]) == merchant_id
            ]
        if not rows:
            return _error(
                "candidates_not_found",
                "No ad candidates found for the provided query or merchant_id.",
                query=query,
                merchant_id=merchant_id,
                ranked_candidates=[],
            )

        growth_scores = _score_product_rows(rows)
        roi_scores = _normalize_values(rows, "historical_roi")
        keyword_scores = _normalize_values(rows, "keyword_coverage")
        ranked_candidates: list[dict[str, Any]] = []
        for row in rows:
            product_id = str(row["product_id"])
            recall = recall_by_product.get(product_id, {})
            recall_score = _as_float(recall, "recall_score")
            refund_risk_penalty = min(_as_float(row, "refund_rate") * 0.5, 0.08)
            if not query:
                final_score = (
                    0.75 * growth_scores[product_id]
                    + 0.15 * roi_scores.get(product_id, 0.0)
                    + 0.10 * keyword_scores.get(product_id, 0.0)
                    - refund_risk_penalty
                )
            else:
                final_score = (
                    0.50 * growth_scores[product_id]
                    + 0.30 * recall_score
                    + 0.15 * roi_scores.get(product_id, 0.0)
                    + 0.05 * keyword_scores.get(product_id, 0.0)
                    - refund_risk_penalty
                )
            recommendation = "适合作为商品级广告主推品"
            if _risk_flags(row):
                recommendation = "可作为候选，但需先处理风险或小流量验证"
            if final_score < 0.35:
                recommendation = "不建议作为优先加价主推品"

            ranked_candidates.append(
                {
                    "product_id": product_id,
                    "product_name": row["product_name"],
                    "merchant_id": row["merchant_id"],
                    "final_score": round(max(final_score, 0.0), 3),
                    "score_breakdown": {
                        "product_growth_score": round(growth_scores[product_id], 3),
                        "recall_score": round(recall_score, 3),
                        "roi_score": round(roi_scores.get(product_id, 0.0), 3),
                        "keyword_coverage_score": round(keyword_scores.get(product_id, 0.0), 3),
                        "refund_risk_penalty": round(refund_risk_penalty, 3),
                    },
                    "recall_path": recall.get("recall_path"),
                    "matched_terms": recall.get("matched_terms"),
                    "recommendation": recommendation,
                    "risk_flags": _risk_flags(row),
                }
            )

        ranked_candidates.sort(
            key=lambda item: (
                item["final_score"],
                item["score_breakdown"]["product_growth_score"],
            ),
            reverse=True,
        )
        for index, candidate in enumerate(ranked_candidates[:top_k], start=1):
            candidate["rank"] = index

        return _ok(
            query=query,
            merchant_id=merchant_id,
            top_k=top_k,
            recall_paths_used=recall_result.get("recall_paths_used", []),
            ranked_candidates=ranked_candidates[:top_k],
            method="0.50 growth + 0.30 recall + 0.15 ROI + 0.05 keyword coverage - refund risk",
        )
    except Exception as error:  # pragma: no cover
        return _error("tool_error", str(error), query=query, merchant_id=merchant_id)


def simulate_bid_strategy(product_id: str, bid_multiplier: float) -> dict[str, Any]:
    """Return the closest synthetic bid experiment for a requested multiplier."""

    try:
        with get_connection() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM ad_bid_experiments
                    WHERE product_id = ?
                    ORDER BY ABS(bid_multiplier - ?), bid_multiplier
                    """,
                    (product_id, bid_multiplier),
                ).fetchall()
            ]
        if not rows:
            return _error(
                "product_not_found",
                f"No bid experiment found for product_id={product_id}.",
                product_id=product_id,
            )

        row = rows[0]
        roi = _as_float(row, "roi")
        roi_status = "pass" if roi >= 3.0 else "risk"
        risk_note = (
            "ROI 高于目标阈值，但需继续监控退款率"
            if roi_status == "pass"
            else "ROI 低于目标阈值，建议降低出价或启用智能调价保护"
        )
        return _ok(
            product_id=product_id,
            requested_bid_multiplier=round(bid_multiplier, 3),
            matched_group=row["group_name"],
            bid_multiplier=_as_float(row, "bid_multiplier"),
            cpc=_as_float(row, "cpc"),
            impressions=_as_int(row, "impressions"),
            clicks=_as_int(row, "clicks"),
            ctr=_as_float(row, "ctr"),
            cvr=_as_float(row, "cvr"),
            orders=_as_int(row, "orders"),
            revenue=_as_float(row, "revenue"),
            ad_cost=_as_float(row, "ad_cost"),
            roi=roi,
            roi_status=roi_status,
            risk_note=risk_note,
        )
    except Exception as error:  # pragma: no cover
        return _error("tool_error", str(error), product_id=product_id)


def compare_poi_vs_product_ads(merchant_id: str) -> dict[str, Any]:
    """Compare POI-level and product-level ad baselines for one merchant."""

    try:
        with get_connection() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM poi_level_ads_baseline
                    WHERE merchant_id = ?
                    ORDER BY
                        CASE campaign_type
                            WHEN 'poi_level' THEN 1
                            WHEN 'product_level' THEN 2
                            WHEN 'product_level_with_smart_bid' THEN 3
                            ELSE 4
                        END
                    """,
                    (merchant_id,),
                ).fetchall()
            ]
        if not rows:
            return _error(
                "merchant_not_found",
                f"No POI vs product ad baseline found for merchant_id={merchant_id}.",
                merchant_id=merchant_id,
                comparison=[],
            )

        comparison = [
            {
                "campaign_type": row["campaign_type"],
                "campaign_id": row["campaign_id"],
                "impressions": _as_int(row, "impressions"),
                "clicks": _as_int(row, "clicks"),
                "orders": _as_int(row, "orders"),
                "revenue": _as_float(row, "revenue"),
                "ad_cost": _as_float(row, "ad_cost"),
                "ctr": _as_float(row, "ctr"),
                "cvr": _as_float(row, "cvr"),
                "roi": _as_float(row, "roi"),
                "notes": row["notes"],
            }
            for row in rows
        ]
        by_type = {item["campaign_type"]: item for item in comparison}
        insights = [
            "商品级广告在高意向 Query 下 CTR 和 CVR 更高",
            "智能调价可在提升订单的同时维持 ROI 下限",
        ]
        if "poi_level" in by_type and "product_level" in by_type:
            ctr_lift = by_type["product_level"]["ctr"] - by_type["poi_level"]["ctr"]
            cvr_lift = by_type["product_level"]["cvr"] - by_type["poi_level"]["cvr"]
            insights.append(
                f"商品级广告相对 POI 级广告 CTR 提升 {ctr_lift * 100:.2f} 个百分点，"
                f"CVR 提升 {cvr_lift * 100:.2f} 个百分点"
            )
        return _ok(merchant_id=merchant_id, comparison=comparison, insights=insights)
    except Exception as error:  # pragma: no cover
        return _error("tool_error", str(error), merchant_id=merchant_id, comparison=[])


def group_ranked_candidates_by_merchant(
    candidates: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group ranked candidates by merchant for report summaries."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[str(candidate.get("merchant_id", ""))].append(candidate)
    return dict(grouped)
