"""FastAPI routes for running the BusinessInsight Agent."""

from time import perf_counter

from fastapi import APIRouter, HTTPException

from app.agent.graph import run_agent
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.cache_service import CacheService

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run the agent state machine for a natural-language business question."""

    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty.")

    cache = CacheService()
    cache_key = cache.build_key(query)
    if request.use_cache:
        cache_started_at = perf_counter()
        cached_payload = cache.get_cache(cache_key)
        if cached_payload is not None:
            latency_ms = int((perf_counter() - cache_started_at) * 1000)
            payload = cache.build_cache_hit_response(query, cache_key, cached_payload, latency_ms)
            return AnalyzeResponse(**payload)

    try:
        result = run_agent(query, cache_key=cache_key if request.use_cache else None)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {error}") from error

    latency_ms = int(result.get("latency_ms", 0))
    if not result.get("final_answer"):
        errors = result.get("errors") or [{"error": "missing final_answer"}]
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {errors}")

    payload = {
        "trace_id": result["trace_id"],
        "intent": result.get("intent", ""),
        "answer": result["final_answer"],
        "tool_results": result.get("tool_results", {}),
        "retrieved_docs": result.get("retrieved_docs", []),
        "latency_ms": latency_ms,
        "cached": False,
        "cache_key": cache_key if request.use_cache else None,
    }
    if request.use_cache:
        cache.set_cache(cache_key, payload)

    return AnalyzeResponse(**payload)
