"""Run rule-based Agent evaluations against local eval cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent.graph import run_agent
from app.db.init_db import initialize_database

from evals.metrics import calculate_case_score

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "eval_cases.json"


def load_eval_cases(cases_path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    """Load evaluation cases from JSON."""

    with Path(cases_path).open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("eval_cases.json must contain a list of cases.")
    return cases


def run_evaluations(cases_path: str | Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    """Run all eval cases and return per-case plus aggregate metrics."""

    initialize_database()
    cases = load_eval_cases(cases_path)
    case_results: list[dict[str, Any]] = []

    for eval_case in cases:
        agent_result = run_agent(eval_case["query"])
        score_detail = calculate_case_score(agent_result, eval_case)
        case_results.append(
            {
                "case_id": eval_case["case_id"],
                "query": eval_case["query"],
                "expected_intent": eval_case["expected_intent"],
                "actual_intent": agent_result.get("intent", ""),
                "trace_id": agent_result.get("trace_id", ""),
                "latency_ms": agent_result.get("latency_ms", 0),
                **score_detail,
            }
        )

    case_count = len(case_results)
    if case_count == 0:
        overall_metrics = {
            "intent_accuracy": 0.0,
            "avg_keyword_coverage": 0.0,
            "evidence_hit_rate": 0.0,
            "avg_entity_coverage": 0.0,
            "avg_tool_result_key_coverage": 0.0,
            "avg_trace_field_coverage": 0.0,
            "error_expectation_accuracy": 0.0,
            "forbidden_keyword_pass_rate": 0.0,
            "avg_latency_ms": 0.0,
            "avg_score": 0.0,
        }
    else:
        overall_metrics = {
            "intent_accuracy": round(
                sum(item["intent_accuracy"] for item in case_results) / case_count,
                6,
            ),
            "avg_keyword_coverage": round(
                sum(item["keyword_coverage"] for item in case_results) / case_count,
                6,
            ),
            "evidence_hit_rate": round(
                sum(item["evidence_hit"] for item in case_results) / case_count,
                6,
            ),
            "avg_entity_coverage": round(
                sum(item["entity_coverage"] for item in case_results) / case_count,
                6,
            ),
            "avg_tool_result_key_coverage": round(
                sum(item["tool_result_key_coverage"] for item in case_results) / case_count,
                6,
            ),
            "avg_trace_field_coverage": round(
                sum(item["trace_field_coverage"] for item in case_results) / case_count,
                6,
            ),
            "error_expectation_accuracy": round(
                sum(item["error_expectation"] for item in case_results) / case_count,
                6,
            ),
            "forbidden_keyword_pass_rate": round(
                sum(item["forbidden_keyword_pass"] for item in case_results) / case_count,
                6,
            ),
            "avg_latency_ms": round(
                sum(item["latency_ms"] for item in case_results) / case_count,
                2,
            ),
            "avg_score": round(
                sum(item["score"] for item in case_results) / case_count,
                6,
            ),
        }

    return {
        "case_count": case_count,
        "overall_metrics": overall_metrics,
        "case_results": case_results,
    }


def main() -> None:
    """CLI entrypoint for `python -m evals.run_eval`."""

    result = run_evaluations()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
