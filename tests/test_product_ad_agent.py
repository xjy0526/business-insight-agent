from app.agent.graph import run_agent
from app.db.init_db import initialize_database


def setup_module():
    initialize_database()


def test_product_ad_strategy_agent_flow():
    result = run_agent("商户 M001 应该优先推哪些商品做搜索广告？")

    assert result["intent"] in {"product_ad_strategy", "sku_mining"}
    assert "product_ad" in result["tool_results"]
    assert "主推品" in result["final_answer"]
    assert "CVR" in result["final_answer"]
    assert "GMV占比" in result["final_answer"]
    assert "ROI" in result["final_answer"]


def test_bid_recommendation_agent_flow():
    result = run_agent("P1001 如果做主推品加价，合理出价区间是多少？")

    assert result["intent"] == "bid_recommendation"
    assert "product_ad" in result["tool_results"]
    assert "PCVR" in result["final_answer"]
    assert "ROI" in result["final_answer"]
    assert "CPC" in result["final_answer"]
    assert "出价区间" in result["final_answer"]


def test_sku_recall_agent_flow():
    result = run_agent("用户搜索 水光补水 时，应该召回哪些商品，为什么？")

    assert result["intent"] == "sku_recall"
    assert "product_ad" in result["tool_results"]
    assert any(
        keyword in result["final_answer"]
        for keyword in ["keyword_inverted", "query_expansion", "vector_match"]
    )


def test_existing_business_diagnosis_still_runs():
    result = run_agent("商品 P1001 最近 GMV 为什么下降？")

    assert result["intent"] == "business_diagnosis"
    assert "period_comparison" in result["tool_results"]
    assert "GMV" in result["final_answer"]
