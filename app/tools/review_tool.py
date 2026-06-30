"""Review analysis tool for product-level customer feedback."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.db.database import get_connection

NEGATIVE_RATING_THRESHOLD = 2
TOPIC_RULES = [
    ("效果不明显", ["效果不明显", "维持时间", "补水效果", "效果弱"]),
    ("等待时间长", ["等待时间", "等了", "排队", "预约等待", "到店排队"]),
    ("服务体验不舒服", ["服务体验", "不舒服", "刺痛", "手法", "体验不好"]),
    ("推销感强", ["推销", "办卡", "加项目", "强推"]),
    ("描述不符", ["描述", "不符", "虚标", "宣传"]),
]
LEGACY_TOPIC_LABELS = {
    "效果不明显": "服务效果",
    "等待时间长": "预约履约",
    "服务体验不舒服": "到店体验",
    "推销感强": "销售体验",
    "描述不符": "描述不符",
    "其他": "其他",
}


def _safe_divide(numerator: float, denominator: float) -> float:
    """Return a rounded ratio without raising ZeroDivisionError."""

    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _percent_change(current_value: float, baseline_value: float) -> float | None:
    """Return relative change while handling a zero baseline."""

    if baseline_value == 0:
        return None
    return round((current_value - baseline_value) / baseline_value, 6)


def _fetch_reviews(product_id: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Load reviews for one product and date range."""

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT review_id, rating, content, review_date
            FROM reviews
            WHERE product_id = ?
              AND review_date BETWEEN ? AND ?
            ORDER BY review_date, review_id
            """,
            (product_id, start_date, end_date),
        ).fetchall()

    return [dict(row) for row in rows]


def _match_topics(content: str) -> list[tuple[str, list[str]]]:
    """Return matched topic names and matched keywords for one review."""

    matched: list[tuple[str, list[str]]] = []
    for topic, keywords in TOPIC_RULES:
        matched_keywords = [keyword for keyword in keywords if keyword in content]
        if matched_keywords:
            matched.append((topic, matched_keywords))
    return matched or [("其他", [])]


def _negative_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter negative reviews according to the configured rating threshold."""

    return [
        review for review in reviews if int(review["rating"]) <= NEGATIVE_RATING_THRESHOLD
    ]


def _build_topic_buckets(negative_reviews: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group negative reviews into keyword-based topic buckets."""

    topic_buckets: dict[str, dict[str, Any]] = {}
    for review in negative_reviews:
        content = str(review["content"])
        for topic, matched_keywords in _match_topics(content):
            bucket = topic_buckets.setdefault(
                topic,
                {
                    "topic": topic,
                    "count": 0,
                    "keywords": [],
                    "sample_reviews": [],
                },
            )
            bucket["count"] += 1
            bucket["keywords"] = sorted(set(bucket["keywords"]) | set(matched_keywords))
            if len(bucket["sample_reviews"]) < 3:
                bucket["sample_reviews"].append(
                    {
                        "review_id": review["review_id"],
                        "rating": int(review["rating"]),
                        "content": review["content"],
                        "review_date": review["review_date"],
                    }
                )
    return topic_buckets


def _build_topic_distribution(
    topic_buckets: dict[str, dict[str, Any]],
    negative_review_count: int,
) -> list[dict[str, Any]]:
    """Convert topic buckets into sorted distribution rows."""

    topic_distribution = []
    for bucket in topic_buckets.values():
        count = int(bucket["count"])
        topic_distribution.append(
            {
                "topic": bucket["topic"],
                "count": count,
                "share": _safe_divide(count, negative_review_count),
                "keywords": bucket["keywords"],
                "sample_reviews": bucket["sample_reviews"],
            }
        )
    topic_distribution.sort(key=lambda item: (item["count"], item["topic"]), reverse=True)
    return topic_distribution


def _average_rating(reviews: list[dict[str, Any]]) -> float:
    """Return average rating rounded for display."""

    if not reviews:
        return 0.0
    return round(sum(int(review["rating"]) for review in reviews) / len(reviews), 4)


def _sample_negative_reviews(negative_reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a small inspectable sample of negative reviews."""

    return [
        {
            "review_id": review["review_id"],
            "rating": int(review["rating"]),
            "content": review["content"],
            "review_date": review["review_date"],
        }
        for review in negative_reviews[:5]
    ]


def _review_summary(
    product_id: str,
    start_date: str,
    end_date: str,
    top_topics: list[str],
) -> str:
    """Build a compact Chinese summary for review topics."""

    if top_topics:
        return (
            f"{product_id} {start_date} 至 {end_date} 差评主要集中在"
            f"{'、'.join(top_topics[:2])}。"
        )
    return f"{product_id} {start_date} 至 {end_date} 暂无足够差评主题证据。"


def _legacy_topics(topic_distribution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return backward-compatible topic rows used by older reports."""

    return [
        {
            "topic": topic["topic"],
            "label": LEGACY_TOPIC_LABELS.get(topic["topic"], topic["topic"]),
            "keywords": topic["keywords"],
            "negative_review_count": topic["count"],
            "negative_share": topic["share"],
            "sample_reviews": topic["sample_reviews"],
        }
        for topic in topic_distribution
    ]


def analyze_review_topics(product_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Analyze negative-review themes for one product and date range."""

    reviews = _fetch_reviews(product_id, start_date, end_date)
    negative_reviews = _negative_reviews(reviews)
    rating_distribution = Counter(str(review["rating"]) for review in reviews)
    topic_distribution = _build_topic_distribution(
        _build_topic_buckets(negative_reviews),
        len(negative_reviews),
    )
    avg_rating = _average_rating(reviews)
    top_topics = [topic["topic"] for topic in topic_distribution[:3]]
    sample_negative_reviews = _sample_negative_reviews(negative_reviews)
    summary = _review_summary(product_id, start_date, end_date, top_topics)

    return {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date,
        "review_count": len(reviews),
        "avg_rating": avg_rating,
        "average_rating": avg_rating,
        "negative_review_count": len(negative_reviews),
        "negative_review_rate": _safe_divide(len(negative_reviews), len(reviews)),
        "rating_distribution": dict(sorted(rating_distribution.items())),
        "topic_distribution": topic_distribution,
        "topics": _legacy_topics(topic_distribution),
        "top_topics": top_topics,
        "sample_negative_reviews": sample_negative_reviews,
        "summary": summary,
    }


def compare_review_periods(
    product_id: str,
    current_start: str,
    current_end: str,
    baseline_start: str,
    baseline_end: str,
) -> dict[str, Any]:
    """Compare review quality and negative topics across two periods."""

    current = analyze_review_topics(product_id, current_start, current_end)
    baseline = analyze_review_topics(product_id, baseline_start, baseline_end)
    changes = {
        "avg_rating": {
            "current": current["avg_rating"],
            "baseline": baseline["avg_rating"],
            "absolute_change": round(current["avg_rating"] - baseline["avg_rating"], 6),
            "percent_change": _percent_change(current["avg_rating"], baseline["avg_rating"]),
        },
        "negative_review_rate": {
            "current": current["negative_review_rate"],
            "baseline": baseline["negative_review_rate"],
            "absolute_change": round(
                current["negative_review_rate"] - baseline["negative_review_rate"],
                6,
            ),
            "percent_change": _percent_change(
                current["negative_review_rate"],
                baseline["negative_review_rate"],
            ),
        },
        "negative_review_count": {
            "current": current["negative_review_count"],
            "baseline": baseline["negative_review_count"],
            "absolute_change": current["negative_review_count"]
            - baseline["negative_review_count"],
            "percent_change": _percent_change(
                float(current["negative_review_count"]),
                float(baseline["negative_review_count"]),
            ),
        },
    }

    return {
        "product_id": product_id,
        "current": current,
        "baseline": baseline,
        "changes": changes,
        "summary": (
            f"当前期差评率 {_safe_divide(current['negative_review_rate'] * 100, 1):.2f}%，"
            f"基准期差评率 {_safe_divide(baseline['negative_review_rate'] * 100, 1):.2f}%，"
            f"当前主要主题为 {'、'.join(current['top_topics']) or '暂无'}。"
        ),
    }
