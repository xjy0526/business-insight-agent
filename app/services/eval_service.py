"""Service wrapper for running Agent evaluations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.run_eval import run_evaluations


class EvalService:
    """Application service for automated evaluation runs."""

    def run_evaluations(self, cases_path: str | Path | None = None) -> dict[str, Any]:
        """Run all configured evaluation cases."""

        if cases_path is None:
            return run_evaluations()
        return run_evaluations(cases_path)
