"""Shared API schemas for BusinessInsight Agent."""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str = Field(description="Service health status.")
    service: str = Field(description="Application name.")


class AnalyzeRequest(BaseModel):
    """Request model for running the agent analysis workflow."""

    query: str = Field(description="Natural-language business analysis question.")
    use_cache: bool = Field(default=True, description="Whether to use 5-minute query cache.")


class AnalyzeResponse(BaseModel):
    """Response model for the agent analysis endpoint."""

    trace_id: str = Field(description="Unique trace ID for this analysis run.")
    intent: str = Field(description="Recognized business intent.")
    answer: str = Field(description="Final structured diagnosis answer.")
    tool_results: dict[str, Any] = Field(description="Metric and tool execution results.")
    retrieved_docs: list[dict[str, Any]] = Field(description="RAG evidence documents.")
    latency_ms: int = Field(description="End-to-end request latency in milliseconds.")
    cached: bool = Field(default=False, description="Whether this response came from cache.")
    cache_key: str | None = Field(default=None, description="Cache key associated with this query.")


class TraceResponse(BaseModel):
    """Response model for persisted Agent trace records."""

    trace_id: str = Field(description="Trace ID.")
    user_query: str | None = Field(default=None, description="Original user question.")
    intent: str | None = Field(default=None, description="Recognized intent.")
    entity_id: str | None = Field(default=None, description="Recognized product ID.")
    plan_steps: list[dict[str, Any]] | None = Field(default=None, description="Agent plan steps.")
    tool_results: dict[str, Any] | None = Field(default=None, description="Tool execution results.")
    retrieved_docs: list[dict[str, Any]] | None = Field(default=None, description="RAG evidence.")
    final_answer: str | None = Field(default=None, description="Final answer.")
    reflection_result: dict[str, Any] | None = Field(default=None, description="Reflection result.")
    node_spans: list[dict[str, Any]] | None = Field(
        default=None,
        description="Per-node trace spans.",
    )
    cache_key: str | None = Field(default=None, description="Cache key associated with this trace.")
    cache_hit: bool = Field(
        default=False,
        description="Whether the trace was generated from cache.",
    )
    latency_ms: int | None = Field(default=None, description="Execution latency in milliseconds.")
    error_type: str | None = Field(default=None, description="Top-level error type.")
    created_at: str | None = Field(default=None, description="Trace creation time.")


class EvalRunResponse(BaseModel):
    """Response model for automated evaluation runs."""

    status: str = Field(description="Evaluation run status.")
    case_count: int = Field(description="Number of evaluated cases.")
    overall_metrics: dict[str, Any] = Field(description="Aggregate evaluation metrics.")
    case_results: list[dict[str, Any]] = Field(description="Per-case evaluation results.")
