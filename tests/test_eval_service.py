"""Tests for automated evaluation service."""

from app.services.eval_service import EvalService


def test_eval_service_runs_and_returns_avg_score() -> None:
    """Evaluation service should run local cases and return aggregate metrics."""

    result = EvalService().run_evaluations()

    assert result["case_count"] >= 5
    assert "avg_score" in result["overall_metrics"]
    assert 0 <= result["overall_metrics"]["avg_score"] <= 1
    assert len(result["case_results"]) >= 5
