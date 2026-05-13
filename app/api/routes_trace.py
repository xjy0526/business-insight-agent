"""FastAPI routes for Agent trace observability."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import TraceResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/api/traces", tags=["trace"])


@router.get("", response_model=list[TraceResponse])
def list_traces(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """List recent Agent traces."""

    return TraceService().list_traces(limit=limit)


@router.get("/{trace_id}", response_model=TraceResponse)
def get_trace(trace_id: str) -> dict:
    """Return one Agent trace by trace_id."""

    trace = TraceService().get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"trace_id not found: {trace_id}")
    return trace
