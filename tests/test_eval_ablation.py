"""Tests for eval modes, ablation summaries, and threshold checks."""

import json

from app.config import get_settings
from app.services.eval_service import EvalService
from evals.run_eval import (
    build_eval_summary,
    check_golden_answer_coverage,
    load_eval_history,
    run_all_modes,
    run_evaluations,
    write_eval_summary,
)


def _write_small_cases(tmp_path) -> str:
    """Create a tiny eval case file for fast ablation tests."""

    cases = [
        {
            "case_id": "small_001",
            "query": "商品 P1001 最近 GMV 为什么下降？",
            "expected_intent": "business_diagnosis",
            "expected_tools": ["metrics_tool", "rag_tool"],
            "expected_keywords": ["GMV", "证据来源", "优化建议"],
            "expected_evidence_sources": ["campaign_rules.md"],
            "expected_entity_ids": ["P1001"],
            "expected_tool_result_keys": ["period_comparison", "rag_search"],
            "expected_trace_fields": ["trace_id", "node_spans", "final_answer"],
        }
    ]
    path = tmp_path / "small_eval_cases.json"
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_run_eval_full_agent_mode(tmp_path) -> None:
    """full_agent mode should run and return an avg_score."""

    result = run_evaluations(_write_small_cases(tmp_path), mode="full_agent")

    assert result["mode"] == "full_agent"
    assert "avg_score" in result["overall_metrics"]
    assert 0 <= result["overall_metrics"]["avg_score"] <= 1


def test_run_eval_no_rag_mode(tmp_path) -> None:
    """no_rag mode should disable retrieved docs and mark RAG disabled."""

    result = run_evaluations(_write_small_cases(tmp_path), mode="no_rag")

    assert result["mode"] == "no_rag"
    assert result["case_results"][0]["retrieved_docs_count"] == 0
    assert "rag" in result["case_results"][0]["disabled_components"]


def test_run_eval_all_modes(tmp_path) -> None:
    """all mode suite should include full_agent and no_rag."""

    results = run_all_modes(_write_small_cases(tmp_path))
    summary = build_eval_summary(results)

    assert {"full_agent", "no_rag", "mock_only"}.issubset(results)
    assert "full_agent" in summary["modes"]
    assert "no_rag_vs_full" in summary["ablation_delta"]


def test_fail_under_threshold(tmp_path) -> None:
    """Threshold summary should pass low thresholds and fail impossible ones."""

    result = run_evaluations(_write_small_cases(tmp_path), mode="full_agent")

    low_threshold = build_eval_summary({"full_agent": result}, fail_under=0.0)
    high_threshold = build_eval_summary({"full_agent": result}, fail_under=1.01)

    assert low_threshold["threshold_check"]["pass"] is True
    assert high_threshold["threshold_check"]["pass"] is False


def test_golden_answer_coverage() -> None:
    """Golden-answer sketches should score expected answer keywords."""

    score = check_golden_answer_coverage(
        {"final_answer": "报告包含 GMV 贡献度、Review Tool 和证据来源。"},
        {"must_include_keywords": ["GMV 贡献度", "Review Tool", "证据来源"]},
    )

    assert score == 1.0


def test_write_eval_summary_updates_history(monkeypatch, tmp_path) -> None:
    """Writing eval summaries should append JSONL history and Markdown trend report."""

    history_path = tmp_path / "eval_history.jsonl"
    report_path = tmp_path / "eval_history_report.md"
    monkeypatch.setenv("EVAL_HISTORY_PATH", str(history_path))
    monkeypatch.setenv("EVAL_HISTORY_REPORT_PATH", str(report_path))
    get_settings.cache_clear()

    summary = build_eval_summary(
        {
            "full_agent": {
                "overall_metrics": {
                    "avg_score": 0.9,
                    "intent_accuracy": 1.0,
                    "evidence_hit_rate": 1.0,
                    "avg_tool_result_key_coverage": 1.0,
                    "avg_reflection_quality": 1.0,
                    "security_flag_pass_rate": 1.0,
                    "avg_golden_answer_coverage": 1.0,
                    "avg_latency_ms": 1.0,
                    "p95_latency_ms": 1,
                }
            }
        }
    )
    write_eval_summary(summary, tmp_path / "summary.json")

    assert load_eval_history(history_path)
    assert "Eval 历史趋势报告" in report_path.read_text(encoding="utf-8")
    get_settings.cache_clear()


def test_eval_service_all_modes(tmp_path) -> None:
    """EvalService should expose all-modes summaries for the API layer."""

    result = EvalService().run_evaluations(
        cases_path=_write_small_cases(tmp_path),
        all_modes=True,
    )

    assert result["mode"] == "all_modes"
    assert "modes" in result
    assert "full_agent" in result["modes"]
    assert result["ablation_results"]


def test_eval_service_single_ablation_mode_keeps_full_agent_threshold(tmp_path) -> None:
    """Single ablation API runs should preserve full_agent as threshold baseline."""

    result = EvalService().run_evaluations(
        cases_path=_write_small_cases(tmp_path),
        mode="no_rag",
        fail_under=0.0,
    )

    assert result["mode"] == "no_rag"
    assert {"no_rag", "full_agent"}.issubset(result["summary"]["modes"])
    assert result["summary"]["threshold_check"]["pass"] is True
