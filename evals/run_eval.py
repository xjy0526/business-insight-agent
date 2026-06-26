"""Run rule-based Agent evaluations against local eval cases."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent.graph import run_agent
from app.config import get_settings
from app.db.init_db import initialize_database
from app.services.trace_service import TraceService

from evals.metrics import calculate_case_score

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "eval_cases.json"
DEFAULT_SUMMARY_PATH = Path(__file__).resolve().parent / "eval_latest_summary.json"
DEFAULT_GOLDEN_ANSWERS_PATH = Path(__file__).resolve().parent / "golden_answers.json"
EVAL_MODES: dict[str, dict[str, Any]] = {
    "full_agent": {
        "description": "完整链路，启用 Metrics、Review/Campaign、RAG 和 Reflection。",
        "controls": {},
    },
    "no_rag": {
        "description": "禁用 RAG，检验知识检索对证据命中的贡献。",
        "controls": {"disable_rag": True},
    },
    "no_review_campaign": {
        "description": "禁用 Review Tool 和 Campaign Tool，保留基础指标与 RAG。",
        "controls": {"disable_review_campaign": True},
    },
    "no_reflection": {
        "description": "禁用 Reflection Evidence Checker，检验证据校验的贡献。",
        "controls": {"disable_reflection": True},
    },
    "no_metrics_tool": {
        "description": "禁用 Metrics Tool，仅使用 RAG 与 fallback 报告。",
        "controls": {"disable_metrics": True, "disable_review_campaign": True},
    },
    "mock_only": {
        "description": "尽量只使用 mock/fallback，不调用业务工具、RAG 或 Reflection。",
        "controls": {"mock_only": True},
    },
}
ALL_MODE_NAMES = list(EVAL_MODES)


def load_eval_cases(cases_path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    """Load evaluation cases from JSON."""

    with Path(cases_path).open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("eval_cases.json must contain a list of cases.")
    return cases


def load_golden_answers(
    golden_path: str | Path = DEFAULT_GOLDEN_ANSWERS_PATH,
) -> dict[str, dict[str, Any]]:
    """Load optional golden-answer expectations by case_id."""

    path = Path(golden_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        parsed = json.load(file)
    return parsed if isinstance(parsed, dict) else {}


def check_golden_answer_coverage(
    agent_result: dict[str, Any],
    golden_case: dict[str, Any] | None,
) -> float:
    """Return keyword coverage against a human-curated golden answer sketch."""

    if not golden_case:
        return 1.0
    expected_keywords = golden_case.get("must_include_keywords", [])
    if not expected_keywords:
        return 1.0
    answer = agent_result.get("final_answer") or ""
    matched = sum(1 for keyword in expected_keywords if keyword in answer)
    return round(matched / len(expected_keywords), 6)


def _build_case_result(
    eval_case: dict[str, Any],
    agent_result: dict[str, Any],
    score_detail: dict[str, Any],
    golden_coverage: float,
) -> dict[str, Any]:
    """Build one per-case eval result row."""

    return {
        "case_id": eval_case["case_id"],
        "query": eval_case["query"],
        "expected_intent": eval_case["expected_intent"],
        "actual_intent": agent_result.get("intent", ""),
        "trace_id": agent_result.get("trace_id", ""),
        "latency_ms": agent_result.get("latency_ms", 0),
        "retrieved_docs_count": len(agent_result.get("retrieved_docs", [])),
        "disabled_components": agent_result.get("disabled_components", []),
        "golden_answer_coverage": golden_coverage,
        **score_detail,
    }


def _average_metric(case_results: list[dict[str, Any]], key: str) -> float:
    """Average one numeric metric across case results."""

    return round(sum(item[key] for item in case_results) / len(case_results), 6)


def _aggregate_overall_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-case metrics into the summary shape."""

    case_count = len(case_results)
    if case_count == 0:
        return _empty_overall_metrics()

    latencies = [int(item["latency_ms"]) for item in case_results]
    return {
        "intent_accuracy": _average_metric(case_results, "intent_accuracy"),
        "avg_keyword_coverage": _average_metric(case_results, "keyword_coverage"),
        "evidence_hit_rate": _average_metric(case_results, "evidence_hit"),
        "avg_entity_coverage": _average_metric(case_results, "entity_coverage"),
        "avg_tool_result_key_coverage": _average_metric(
            case_results,
            "tool_result_key_coverage",
        ),
        "avg_ad_recommendation_fields": _average_metric(
            case_results,
            "ad_recommendation_fields",
        ),
        "avg_bid_guardrail": _average_metric(case_results, "bid_guardrail"),
        "avg_sku_recall_fields": _average_metric(case_results, "sku_recall_fields"),
        "avg_poi_vs_product_comparison": _average_metric(
            case_results,
            "poi_vs_product_comparison",
        ),
        "avg_claim_evidence_alignment": _average_metric(
            case_results,
            "claim_evidence_alignment",
        ),
        "avg_root_cause_or_recommendation_hit": _average_metric(
            case_results,
            "root_cause_or_recommendation_hit",
        ),
        "avg_trace_field_coverage": _average_metric(case_results, "trace_field_coverage"),
        "error_expectation_accuracy": _average_metric(case_results, "error_expectation"),
        "forbidden_keyword_pass_rate": _average_metric(case_results, "forbidden_keyword_pass"),
        "avg_reflection_quality": _average_metric(case_results, "reflection_quality"),
        "security_flag_pass_rate": _average_metric(case_results, "security_flag"),
        "avg_golden_answer_coverage": _average_metric(
            case_results,
            "golden_answer_coverage",
        ),
        "avg_latency_ms": round(sum(latencies) / case_count, 2),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "avg_score": _average_metric(case_results, "score"),
    }


def _empty_overall_metrics() -> dict[str, Any]:
    """Return the aggregate metric shape for an empty case file."""

    return {
        "intent_accuracy": 0.0,
        "avg_keyword_coverage": 0.0,
        "evidence_hit_rate": 0.0,
        "avg_entity_coverage": 0.0,
        "avg_tool_result_key_coverage": 0.0,
        "avg_ad_recommendation_fields": 0.0,
        "avg_bid_guardrail": 0.0,
        "avg_sku_recall_fields": 0.0,
        "avg_poi_vs_product_comparison": 0.0,
        "avg_claim_evidence_alignment": 0.0,
        "avg_root_cause_or_recommendation_hit": 0.0,
        "avg_trace_field_coverage": 0.0,
        "error_expectation_accuracy": 0.0,
        "forbidden_keyword_pass_rate": 0.0,
        "avg_reflection_quality": 0.0,
        "security_flag_pass_rate": 0.0,
        "avg_golden_answer_coverage": 0.0,
        "avg_latency_ms": 0.0,
        "p95_latency_ms": 0,
        "avg_score": 0.0,
    }


def _now_iso() -> str:
    """Return current UTC timestamp for eval summary artifacts."""

    return datetime.now(UTC).isoformat()


def _percentile(values: list[int], percentile: float) -> int:
    """Calculate a nearest-rank percentile for eval latency values."""

    if not values:
        return 0
    sorted_values = sorted(values)
    index = max(
        0,
        min(len(sorted_values) - 1, int(percentile * len(sorted_values) + 0.999999) - 1),
    )
    return sorted_values[index]


def build_eval_gate(overall_metrics: dict[str, Any]) -> dict[str, Any]:
    """Build threshold gate status for CI and release checks."""

    settings = get_settings()
    checks = {
        "avg_score": {
            "actual": overall_metrics.get("avg_score", 0.0),
            "threshold": settings.eval_min_avg_score,
            "pass": overall_metrics.get("avg_score", 0.0) >= settings.eval_min_avg_score,
        },
        "intent_accuracy": {
            "actual": overall_metrics.get("intent_accuracy", 0.0),
            "threshold": settings.eval_min_intent_accuracy,
            "pass": overall_metrics.get("intent_accuracy", 0.0)
            >= settings.eval_min_intent_accuracy,
        },
    }
    return {
        "pass": all(check["pass"] for check in checks.values()),
        "checks": checks,
    }


def run_evaluations(
    cases_path: str | Path = DEFAULT_CASES_PATH,
    disabled_components: list[str] | None = None,
    mode: str = "full_agent",
    controls: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all eval cases and return per-case plus aggregate metrics."""

    if mode not in EVAL_MODES:
        raise ValueError(f"Unsupported eval mode: {mode}")

    initialize_database()
    cases = load_eval_cases(cases_path)
    golden_answers = load_golden_answers(get_settings().eval_golden_answers_path)
    case_results: list[dict[str, Any]] = []
    mode_controls = {**EVAL_MODES[mode]["controls"], **(controls or {})}

    for eval_case in cases:
        agent_result = run_agent(
            eval_case["query"],
            disabled_components=disabled_components,
            controls=mode_controls,
        )
        score_detail = calculate_case_score(agent_result, eval_case)
        golden_coverage = check_golden_answer_coverage(
            agent_result,
            golden_answers.get(str(eval_case["case_id"])),
        )
        case_results.append(
            _build_case_result(
                eval_case,
                agent_result,
                score_detail,
                golden_coverage,
            )
        )

    case_count = len(case_results)
    overall_metrics = _aggregate_overall_metrics(case_results)
    trace_stats_snapshot = TraceService().get_trace_stats(limit=max(case_count, 1))

    return {
        "case_count": case_count,
        "mode": mode,
        "mode_description": EVAL_MODES[mode]["description"],
        "controls": mode_controls,
        "overall_metrics": overall_metrics,
        "case_results": case_results,
        "gate": build_eval_gate(overall_metrics),
        "disabled_components": disabled_components or [],
        "trace_stats_snapshot": trace_stats_snapshot,
    }


def _compact_mode_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Return high-signal metrics for summary files and comparison tables."""

    overall = result["overall_metrics"]
    return {
        "avg_score": overall.get("avg_score", 0.0),
        "intent_accuracy": overall.get("intent_accuracy", 0.0),
        "evidence_hit_rate": overall.get("evidence_hit_rate", 0.0),
        "avg_tool_result_key_coverage": overall.get("avg_tool_result_key_coverage", 0.0),
        "avg_ad_recommendation_fields": overall.get("avg_ad_recommendation_fields", 0.0),
        "avg_bid_guardrail": overall.get("avg_bid_guardrail", 0.0),
        "avg_sku_recall_fields": overall.get("avg_sku_recall_fields", 0.0),
        "avg_claim_evidence_alignment": overall.get("avg_claim_evidence_alignment", 0.0),
        "avg_reflection_quality": overall.get("avg_reflection_quality", 0.0),
        "security_flag_pass_rate": overall.get("security_flag_pass_rate", 0.0),
        "avg_golden_answer_coverage": overall.get("avg_golden_answer_coverage", 0.0),
        "avg_latency_ms": overall.get("avg_latency_ms", 0.0),
        "p95_latency_ms": overall.get("p95_latency_ms", 0),
    }


def _build_ablation_delta(modes: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Build mode deltas relative to full_agent."""

    full_metrics = modes.get("full_agent", {})
    deltas: dict[str, dict[str, float]] = {}
    for mode_name, metrics in modes.items():
        if mode_name == "full_agent":
            continue
        deltas[f"{mode_name}_vs_full"] = {
            "avg_score_delta": round(
                metrics.get("avg_score", 0.0) - full_metrics.get("avg_score", 0.0),
                6,
            ),
            "evidence_hit_rate_delta": round(
                metrics.get("evidence_hit_rate", 0.0)
                - full_metrics.get("evidence_hit_rate", 0.0),
                6,
            ),
            "avg_latency_ms_delta": round(
                metrics.get("avg_latency_ms", 0.0) - full_metrics.get("avg_latency_ms", 0.0),
                6,
            ),
        }
    return deltas


def build_eval_summary(
    mode_results: dict[str, dict[str, Any]],
    fail_under: float | None = None,
) -> dict[str, Any]:
    """Build a machine-readable eval summary with optional threshold status."""

    modes = {
        mode_name: _compact_mode_metrics(result)
        for mode_name, result in mode_results.items()
    }
    full_score = modes.get("full_agent", {}).get("avg_score", 0.0)
    threshold_check = {
        "enabled": fail_under is not None,
        "threshold": fail_under,
        "full_agent_avg_score": full_score,
        "pass": True if fail_under is None else full_score >= fail_under,
    }
    return {
        "generated_at": _now_iso(),
        "modes": modes,
        "ablation_delta": _build_ablation_delta(modes),
        "threshold_check": threshold_check,
    }


def write_eval_summary(summary: dict[str, Any], output_path: str | Path) -> None:
    """Write eval summary JSON to disk."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_eval_history(summary)
    write_eval_history_report()


def append_eval_history(summary: dict[str, Any], history_path: str | Path | None = None) -> None:
    """Append one compact eval run to a JSONL history file."""

    path = Path(history_path or get_settings().eval_history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    compact_record = {
        "generated_at": summary.get("generated_at"),
        "modes": summary.get("modes", {}),
        "threshold_check": summary.get("threshold_check", {}),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(compact_record, ensure_ascii=False) + "\n")


def load_eval_history(history_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load historical eval JSONL records while skipping malformed lines."""

    path = Path(history_path or get_settings().eval_history_path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def write_eval_history_report(
    history_path: str | Path | None = None,
    report_path: str | Path | None = None,
    limit: int = 20,
) -> None:
    """Write a Markdown trend report for recent eval runs."""

    records = load_eval_history(history_path)[-limit:]
    path = Path(report_path or get_settings().eval_history_report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Eval 历史趋势报告",
        "",
        (
            "该文件由 `python -m evals.run_eval` 自动更新，"
            "用于观察 avg_score、证据命中率和阈值门禁趋势。"
        ),
        "",
        "| Time | Mode | Avg Score | Evidence Hit | Golden Coverage | Pass |",
        "|---|---|---:|---:|---:|---|",
    ]
    for record in records:
        generated_at = record.get("generated_at", "")
        threshold_pass = record.get("threshold_check", {}).get("pass", True)
        for mode_name, metrics in record.get("modes", {}).items():
            lines.append(
                "| "
                f"{generated_at} | {mode_name} | "
                f"{metrics.get('avg_score', 0):.6f} | "
                f"{metrics.get('evidence_hit_rate', 0):.6f} | "
                f"{metrics.get('avg_golden_answer_coverage', 0):.6f} | "
                f"{threshold_pass} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_all_modes(cases_path: str | Path = DEFAULT_CASES_PATH) -> dict[str, dict[str, Any]]:
    """Run the full ablation suite across all configured modes."""

    return {
        mode_name: run_evaluations(cases_path=cases_path, mode=mode_name)
        for mode_name in ALL_MODE_NAMES
    }


def build_ablation_table(mode_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a compact table for API/frontend consumption."""

    summary = build_eval_summary(mode_results)
    return [
        {
            "mode": mode_name,
            "description": EVAL_MODES[mode_name]["description"],
            **metrics,
            "avg_score_delta_vs_full": summary["ablation_delta"]
            .get(f"{mode_name}_vs_full", {})
            .get("avg_score_delta", 0.0),
            "evidence_hit_rate_delta_vs_full": summary["ablation_delta"]
            .get(f"{mode_name}_vs_full", {})
            .get("evidence_hit_rate_delta", 0.0),
        }
        for mode_name, metrics in summary["modes"].items()
    ]


def run_ablation_suite(cases_path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    """Run all supported ablation modes and return compact comparison rows."""

    return build_ablation_table(run_all_modes(cases_path))


def main() -> None:
    """CLI entrypoint for `python -m evals.run_eval`."""

    parser = argparse.ArgumentParser(description="Run BusinessInsight Agent evals.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="Path to eval cases JSON.")
    parser.add_argument(
        "--mode",
        choices=ALL_MODE_NAMES,
        default=get_settings().eval_mode,
        help="Eval mode to run.",
    )
    parser.add_argument(
        "--all-modes",
        action="store_true",
        help="Run full_agent plus all ablation modes.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_SUMMARY_PATH),
        help="Path to write machine-readable eval summary JSON.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit with non-zero status if full_agent avg_score is below this threshold.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status when eval threshold gate fails.",
    )
    parser.add_argument(
        "--with-ablations",
        action="store_true",
        help="Backward-compatible alias for --all-modes.",
    )
    args = parser.parse_args()

    run_all = args.all_modes or args.with_ablations
    if run_all:
        mode_results = run_all_modes(args.cases)
        summary = build_eval_summary(mode_results, fail_under=args.fail_under)
        write_eval_summary(summary, args.output)
        result = {
            "case_count": mode_results["full_agent"]["case_count"],
            "mode": "all_modes",
            "summary": summary,
            "modes": {
                mode_name: result["overall_metrics"]
                for mode_name, result in mode_results.items()
            },
            "ablation_results": build_ablation_table(mode_results),
            "full_agent": mode_results["full_agent"],
        }
    else:
        result = run_evaluations(args.cases, mode=args.mode)
        mode_results = {args.mode: result}
        if args.mode != "full_agent":
            mode_results["full_agent"] = run_evaluations(args.cases, mode="full_agent")
        summary = build_eval_summary(mode_results, fail_under=args.fail_under)
        write_eval_summary(summary, args.output)
        result["ablation_results"] = []
        result["summary"] = summary
    print(json.dumps(result, ensure_ascii=False, indent=2))

    full_result = mode_results.get("full_agent", result)
    threshold_failed = (
        args.fail_under is not None
        and full_result["overall_metrics"].get("avg_score", 0.0) < args.fail_under
    )
    strict_failed = args.strict and not full_result.get("gate", {}).get("pass", True)
    if threshold_failed or strict_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
