"""Tests for automated evaluation service."""

from app.services.eval_service import EvalService


def test_eval_service_runs_and_returns_avg_score() -> None:
    """Evaluation service should run local cases and return aggregate metrics."""

    result = EvalService().run_evaluations()

    assert result["case_count"] >= 5
    assert "avg_score" in result["overall_metrics"]
    assert "gate" in result
    assert 0 <= result["overall_metrics"]["avg_score"] <= 1
    assert len(result["case_results"]) >= 5


def test_eval_service_can_run_component_ablations() -> None:
    """Evaluation service should expose compact ablation summaries on demand."""

    result = EvalService().run_evaluations(include_ablations=True)

    assert result["ablation_results"]
    assert {item["mode"] for item in result["ablation_results"]} >= {
        "no_metrics_tool",
        "no_rag",
    }
