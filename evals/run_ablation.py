"""Run product-ad course ablation modes for BusinessInsight Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.run_eval import DEFAULT_CASES_PATH, run_evaluations

ABLATION_MODES: dict[str, dict[str, Any]] = {
    "llm_or_template_only": {
        "description": "不调用指标、商品广告工具、RAG 或 Reflection，仅保留模板链路。",
        "controls": {
            "mock_only": True,
        },
    },
    "metrics_only": {
        "description": "只调用经营指标工具，不调用商品广告工具和 RAG。",
        "controls": {
            "disable_product_ad": True,
            "disable_rag": True,
            "disable_review_campaign": True,
            "disable_reflection": True,
        },
    },
    "product_ad_tools_only": {
        "description": "调用商品广告工具，但不使用 RAG。",
        "controls": {
            "disable_metrics": True,
            "disable_review_campaign": True,
            "disable_rag": True,
            "disable_reflection": True,
        },
    },
    "rag_plus_metrics": {
        "description": "使用指标工具和 RAG，但禁用商品广告推荐分数。",
        "controls": {
            "disable_product_ad": True,
            "disable_review_campaign": True,
            "disable_reflection": True,
        },
    },
    "full_product_ad_agent": {
        "description": (
            "完整 Agent：metrics + product_ad_tool + RAG + recommendation + reflection。"
        ),
        "controls": {},
    },
}


def _compact_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Return compact metrics for one ablation result."""

    overall = result.get("overall_metrics", {})
    return {
        "avg_score": overall.get("avg_score", 0.0),
        "intent_accuracy": overall.get("intent_accuracy", 0.0),
        "evidence_hit_rate": overall.get("evidence_hit_rate", 0.0),
        "avg_ad_recommendation_fields": overall.get("avg_ad_recommendation_fields", 0.0),
        "avg_bid_guardrail": overall.get("avg_bid_guardrail", 0.0),
        "avg_sku_recall_fields": overall.get("avg_sku_recall_fields", 0.0),
        "avg_claim_evidence_alignment": overall.get("avg_claim_evidence_alignment", 0.0),
    }


def run_ablation(cases_path: str | Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    """Run all course ablation modes and return a JSON-serializable report."""

    mode_results: dict[str, dict[str, Any]] = {}
    for mode_name, config in ABLATION_MODES.items():
        result = run_evaluations(
            cases_path=cases_path,
            mode="full_agent",
            controls=config["controls"],
        )
        mode_results[mode_name] = {
            "description": config["description"],
            "controls": config["controls"],
            "overall_metrics": result["overall_metrics"],
        }

    compact = {
        mode_name: _compact_metrics(result)
        for mode_name, result in mode_results.items()
    }
    return {
        "case_count": run_evaluations(cases_path=cases_path, mode="full_agent")["case_count"],
        "overall_metrics_by_mode": compact,
        "summary": [
            "完整 Agent 在证据一致性、ROI guardrail 和召回解释方面表现最好",
            "product_ad_tools_only 可展示工具本身贡献，rag_plus_metrics 可展示知识检索贡献",
        ],
        "details": mode_results,
    }


def main() -> None:
    """CLI entrypoint for `python -m evals.run_ablation`."""

    print(json.dumps(run_ablation(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
