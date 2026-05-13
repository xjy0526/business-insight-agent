"""FastAPI routes for automated evaluation runs."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import EvalRunResponse
from app.services.eval_service import EvalService

router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.post("/run", response_model=EvalRunResponse)
def run_eval() -> EvalRunResponse:
    """Run local rule-based Agent evaluations."""

    result = EvalService().run_evaluations()
    return EvalRunResponse(
        status="completed",
        case_count=result["case_count"],
        overall_metrics=result["overall_metrics"],
        case_results=result["case_results"],
    )
