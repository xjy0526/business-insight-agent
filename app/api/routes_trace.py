"""FastAPI routes for Agent trace observability."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import TraceResponse, TraceStatsResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/api/traces", tags=["trace"])


@router.get("", response_model=list[TraceResponse])
def list_traces(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """List recent Agent traces."""

    return TraceService().list_traces(limit=limit)


@router.get("/recent", response_model=list[TraceResponse])
def list_recent_traces(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """List recent Agent traces with an explicit dashboard-friendly path."""

    return TraceService().list_traces(limit=limit)


@router.get("/stats", response_model=TraceStatsResponse)
def get_trace_stats(limit: int = Query(100, ge=1, le=500)) -> dict:
    """Return aggregated observability stats for recent traces."""

    return TraceService().get_trace_stats(limit=limit)


@router.get("/nodes")
def get_node_stats(limit: int = Query(500, ge=1, le=500)) -> list[dict]:
    """Return per-node latency and error stats from trace spans."""

    return TraceService().get_node_stats(limit=limit)


@router.get("/errors")
def get_error_summary(limit: int = Query(500, ge=1, le=500)) -> dict:
    """Return top-level and node-level error summaries."""

    return TraceService().get_error_summary(limit=limit)


@router.get("/{trace_id}", response_model=TraceResponse)
def get_trace(trace_id: str) -> dict:
    """Return one Agent trace by trace_id."""

    trace = TraceService().get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"trace_id not found: {trace_id}")
    return trace
