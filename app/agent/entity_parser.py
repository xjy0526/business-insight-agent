"""Deterministic entity parsing for product-level advertising queries."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedAdEntities:
    """Parsed entities and flags for product-level ad decisions."""

    merchant_id: str | None = None
    product_id: str | None = None
    poi_id: str | None = None
    target_roi: float | None = None
    bid_multiplier: float | None = None
    search_query: str | None = None
    budget_limited: bool = False
    refund_risk_focus: bool = False
    comparison_focus: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict."""

        return asdict(self)


def _first_match(pattern: str, text: str, flags: int = 0) -> str | None:
    """Return the first regex capture or match."""

    match = re.search(pattern, text, flags)
    if not match:
        return None
    return match.group(1) if match.groups() else match.group(0)


def _extract_target_roi(query: str) -> float | None:
    """Extract target ROI from Chinese/English query text."""

    match = re.search(r"(?:目标\s*)?ROI\s*(?:为|=|:|：)?\s*(\d+(?:\.\d+)?)", query, re.I)
    return float(match.group(1)) if match else None


def _extract_bid_multiplier(query: str) -> float | None:
    """Extract bid multiplier from bid-lift phrases."""

    match = re.search(r"(?:加价|提高出价|提价|溢价|上调)\s*(\d+(?:\.\d+)?)\s*%", query)
    if match:
        return round(1 + float(match.group(1)) / 100, 3)
    multiplier = re.search(r"(?:bid_multiplier|出价倍数)\s*[:：=]?\s*(\d+(?:\.\d+)?)", query, re.I)
    return round(float(multiplier.group(1)), 3) if multiplier else None


def _extract_search_query(query: str) -> str | None:
    """Extract natural-language search query from recall-style questions."""

    marker_patterns = [
        r"用户搜索",
        r"搜索词(?:是|为)?",
        r"关键词",
        r"Query\s*(?:是|为)?",
        r"搜索",
    ]
    marker_regex = re.compile("|".join(f"(?:{pattern})" for pattern in marker_patterns), re.I)
    for marker in marker_regex.finditer(query):
        tail = query[marker.end() :].strip()
        tail = re.sub(r"^[\s:=：是为]+", "", tail)
        tail = tail.strip(" \"'“”‘’")
        if not tail:
            continue

        stop_match = re.search(
            r"(?:[\"'“”‘’]?\s*时\b|[\"'“”‘’]?时[，,。?？]?|\s应该\b|应该|[，,。?？；;])",
            tail,
        )
        candidate = tail[: stop_match.start()] if stop_match else tail
        candidate = candidate.strip(" \"'“”‘’")
        candidate = re.sub(r"\s+", "", candidate)
        if candidate:
            return candidate

    known_queries = [
        "水光补水",
        "小气泡清洁",
        "小气泡护理",
        "美甲款式",
        "自然款美睫",
        "双人烤肉",
        "亲子摄影",
        "健身私教体验",
        "洗剪吹造型",
        "火星露营套餐",
    ]
    for known_query in known_queries:
        if known_query in query:
            return known_query
    return None


def parse_ad_entities(query: str) -> ParsedAdEntities:
    """Parse merchant/product/ROI/bid/search entities from a user query."""

    normalized = query.upper()
    merchant_id = _first_match(r"M\d{3}", normalized)
    product_id = _first_match(r"P\d{4}", normalized)
    poi_id = _first_match(r"POI\d{3}", normalized)
    return ParsedAdEntities(
        merchant_id=merchant_id,
        product_id=product_id,
        poi_id=poi_id,
        target_roi=_extract_target_roi(query),
        bid_multiplier=_extract_bid_multiplier(query),
        search_query=_extract_search_query(query),
        budget_limited=any(term in query for term in ("预算有限", "预算很少", "预算不足")),
        refund_risk_focus=any(term in query for term in ("退款率偏高", "履约风险", "售后")),
        comparison_focus=any(
            term in normalized or term in query
            for term in ("POI", "门店级", "商品级", "对比", "升级到商品级")
        ),
    )


def parse_product_ids(query: str) -> list[str]:
    """Extract all explicit product IDs from a user query in display order."""

    product_ids = re.findall(r"\bP\d{4}\b", query.upper())
    return list(dict.fromkeys(product_ids))
