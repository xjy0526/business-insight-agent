from app.db.init_db import initialize_database
from app.tools.product_ad_tool import (
    compare_poi_vs_product_ads,
    mine_high_value_products,
    rank_ad_candidates,
    recall_query_to_sku,
    recommend_bid_range,
    simulate_bid_strategy,
)


def setup_module():
    initialize_database()


def test_mine_high_value_products_for_merchant():
    result = mine_high_value_products("M001")

    assert result["ok"] is True
    assert result["candidates"]
    assert result["candidates"][0]["product_id"] == "P1001"
    assert "product_growth_score" in result["candidates"][0]


def test_recommend_bid_range_for_product():
    result = recommend_bid_range("P1001")

    assert result["ok"] is True
    assert result["pcvr"] == 0.065
    assert result["recommended_cpc_range"][0] > 0
    assert result["max_cpc_by_revenue_roi"] > result["max_cpc_by_profit_roi"]


def test_recall_query_to_sku_returns_multi_path_results():
    result = recall_query_to_sku("水光补水")

    assert result["ok"] is True
    assert result["results"][0]["product_id"] == "P1001"
    assert {"keyword_inverted", "query_expansion", "vector_match"}.issubset(
        set(result["recall_paths_used"])
    )


def test_rank_ad_candidates_fuses_query_and_merchant():
    result = rank_ad_candidates(query="水光补水", merchant_id="M001")

    assert result["ok"] is True
    assert result["ranked_candidates"]
    assert result["ranked_candidates"][0]["product_id"] == "P1001"
    assert "score_breakdown" in result["ranked_candidates"][0]


def test_simulate_bid_strategy_matches_closest_group():
    result = simulate_bid_strategy("P1001", 1.2)

    assert result["ok"] is True
    assert result["matched_group"] == "bid_plus_20"
    assert result["roi_status"] == "pass"


def test_compare_poi_vs_product_ads_for_merchant():
    result = compare_poi_vs_product_ads("M001")

    assert result["ok"] is True
    assert len(result["comparison"]) == 3
    assert any(item["campaign_type"] == "product_level" for item in result["comparison"])
