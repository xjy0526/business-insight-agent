"""FastAPI routes for deterministic product-level advertising tools."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import ProductAdToolResponse
from app.tools.product_ad_tool import (
    compare_poi_vs_product_ads,
    mine_high_value_products,
    rank_ad_candidates,
    recall_query_to_sku,
    recommend_bid_range,
    validate_product_ad_data,
)

router = APIRouter(prefix="/api/product-ad", tags=["product-ad"])


def _response(result: dict) -> ProductAdToolResponse:
    """Wrap raw product-ad tool results in a stable response model."""

    return ProductAdToolResponse(ok=bool(result.get("ok")), result=result)


@router.get("/merchant/{merchant_id}/candidates", response_model=ProductAdToolResponse)
def get_merchant_candidates(
    merchant_id: str,
    top_k: int = Query(5, ge=1, le=20),
) -> ProductAdToolResponse:
    """Return high-value product candidates for a merchant."""

    return _response(mine_high_value_products(merchant_id, top_k=top_k))


@router.get("/product/{product_id}/bid-range", response_model=ProductAdToolResponse)
def get_product_bid_range(
    product_id: str,
    target_roi: float = Query(3.0, gt=0),
) -> ProductAdToolResponse:
    """Return CPC range under a target ROI guardrail."""

    return _response(recommend_bid_range(product_id, target_roi=target_roi))


@router.get("/recall", response_model=ProductAdToolResponse)
def get_query_sku_recall(
    query: str = Query(..., min_length=1),
    merchant_id: str | None = Query(default=None),
    top_k: int = Query(5, ge=1, le=20),
) -> ProductAdToolResponse:
    """Return Query-SKU recall plus fused ranking results."""

    recall = recall_query_to_sku(query, top_k=top_k)
    ranked = rank_ad_candidates(query=query, merchant_id=merchant_id, top_k=top_k)
    return _response(
        {
            "ok": bool(recall.get("ok")) and bool(ranked.get("ok")),
            "query_recall": recall,
            "ranked_candidates": ranked,
        }
    )


@router.get("/compare/{merchant_id}", response_model=ProductAdToolResponse)
def get_poi_product_comparison(merchant_id: str) -> ProductAdToolResponse:
    """Return POI-level vs product-level ad comparison for one merchant."""

    return _response(compare_poi_vs_product_ads(merchant_id))


@router.get("/data-quality", response_model=ProductAdToolResponse)
def get_product_ad_data_quality() -> ProductAdToolResponse:
    """Return synthetic product-ad data quality validation results."""

    return _response(validate_product_ad_data())
