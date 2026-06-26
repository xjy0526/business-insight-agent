"""FastAPI routes for automated evaluation runs."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import EvalRunRequest, EvalRunResponse
from app.services.eval_service import EvalService

router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.post("/run", response_model=EvalRunResponse)
def run_eval(
    request: EvalRunRequest | None = None,
    include_ablations: bool = Query(False),
) -> EvalRunResponse:
    """Run local rule-based Agent evaluations."""

    request = request or EvalRunRequest()
    result = EvalService().run_evaluations(
        include_ablations=include_ablations,
        mode=request.mode,
        all_modes=request.all_modes,
        fail_under=request.fail_under,
    )
    return EvalRunResponse(
        status="completed",
        mode=result.get("mode", request.mode),
        case_count=result["case_count"],
        overall_metrics=result["overall_metrics"],
        case_results=result["case_results"],
        gate=result.get("gate", {}),
        summary=result.get("summary", {}),
        modes=result.get("modes", {}),
        ablation_results=result.get("ablation_results", []),
        threshold_pass=result.get("threshold_pass", True),
        trace_stats_snapshot=result.get("trace_stats_snapshot", {}),
    )
