from evals.metrics import (
    calculate_case_score,
    check_ad_recommendation_fields,
    check_bid_guardrail,
    check_poi_vs_product_comparison,
    check_sku_recall_fields,
)


def test_product_ad_metrics_return_one_for_old_case():
    old_case = {"expected_intent": "business_diagnosis"}
    result = {"final_answer": "GMV 下降", "tool_results": {}}

    assert check_ad_recommendation_fields(result, old_case) == 1.0
    assert check_bid_guardrail(result, old_case) == 1.0
    assert check_sku_recall_fields(result, old_case) == 1.0
    assert check_poi_vs_product_comparison(result, old_case) == 1.0


def test_calculate_case_score_handles_product_ad_case():
    case = {
        "expected_intent": "bid_recommendation",
        "expected_keywords": ["PCVR", "ROI"],
        "expected_tools": ["product_ad_tool"],
        "expected_tool_result_keys": ["product_ad"],
    }
    result = {
        "intent": "bid_recommendation",
        "final_answer": "PCVR、ROI、target_roi、recommended_cpc_range、ROI guardrail",
        "tool_results": {
            "product_ad": {
                "bid_range": {
                    "pcvr": 0.065,
                    "price": 399,
                    "target_roi": 3,
                    "recommended_cpc_range": [1.45, 2.67],
                }
            }
        },
        "retrieved_docs": [],
    }

    score = calculate_case_score(result, case)

    assert score["bid_guardrail"] == 1.0
    assert score["tool_usage"] == 1.0
    assert score["score"] > 0.8
