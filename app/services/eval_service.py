"""Service wrapper for running Agent evaluations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.run_eval import (
    DEFAULT_CASES_PATH,
    build_ablation_table,
    build_eval_summary,
    run_all_modes,
    run_evaluations,
)


class EvalService:
    """Application service for automated evaluation runs."""

    def run_evaluations(
        self,
        cases_path: str | Path | None = None,
        include_ablations: bool = False,
        mode: str = "full_agent",
        all_modes: bool = False,
        fail_under: float | None = None,
    ) -> dict[str, Any]:
        """Run all configured evaluation cases."""

        case_source = cases_path or DEFAULT_CASES_PATH
        if all_modes or include_ablations:
            mode_results = run_all_modes(case_source)
            summary = build_eval_summary(mode_results, fail_under=fail_under)
            full_agent = mode_results["full_agent"]
            return {
                **full_agent,
                "mode": "all_modes",
                "summary": summary,
                "modes": {
                    mode_name: result["overall_metrics"]
                    for mode_name, result in mode_results.items()
                },
                "ablation_results": build_ablation_table(mode_results),
                "threshold_pass": summary["threshold_check"]["pass"],
            }

        result = run_evaluations(case_source, mode=mode)
        mode_results = {mode: result}
        if mode != "full_agent":
            mode_results["full_agent"] = run_evaluations(case_source, mode="full_agent")
        summary = build_eval_summary(mode_results, fail_under=fail_under)
        result["summary"] = summary
        result["threshold_pass"] = summary["threshold_check"]["pass"]
        result["ablation_results"] = []
        return result
