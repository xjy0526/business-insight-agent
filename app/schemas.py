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
    runner: str = Field(default="sequential", description="Agent runner used for this analysis.")
    answer: str = Field(description="Final structured diagnosis answer.")
    tool_results: dict[str, Any] = Field(description="Metric and tool execution results.")
    ad_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Product-level advertising tool results.",
    )
    recommendation_result: dict[str, Any] = Field(
        default_factory=dict,
        description="Unified attribution or recommendation result.",
    )
    evidence_alignment: dict[str, Any] = Field(
        default_factory=dict,
        description="Evidence alignment metadata for major claims.",
    )
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


class TraceStatsResponse(BaseModel):
    """Response model for aggregated trace observability stats."""

    total_traces: int = Field(description="Number of recent traces included.")
    trace_count: int = Field(description="Number of recent traces included.")
    avg_latency_ms: float = Field(description="Average request latency.")
    p50_latency_ms: int = Field(description="Approximate p50 request latency.")
    p95_latency_ms: int = Field(description="Approximate p95 request latency.")
    error_rate: float = Field(description="Share of traces with top-level errors.")
    cache_hit_rate: float = Field(description="Share of traces served from cache.")
    intent_distribution: dict[str, int] = Field(description="Trace count grouped by intent.")
    intent_counts: dict[str, int] = Field(description="Trace count grouped by intent.")
    top_error_nodes: list[dict[str, Any]] = Field(description="Most frequent error nodes.")
    error_type_distribution: dict[str, int] = Field(
        description="Trace count grouped by error type.",
    )
    error_type_counts: dict[str, int] = Field(description="Trace count grouped by error type.")
    slowest_nodes: list[dict[str, Any]] = Field(description="Slowest node latency stats.")
    node_latency_ms: dict[str, dict[str, Any]] = Field(description="Latency stats by node.")
    token_usage_summary: dict[str, Any] = Field(description="Aggregated LLM token usage.")
    provider_status_distribution: dict[str, int] = Field(
        description="Trace count grouped by LLM provider status.",
    )
    alerts: list[dict[str, Any]] = Field(description="Threshold-based trace alerts.")
    recent_traces: list[dict[str, Any]] = Field(description="Recent trace summaries.")


class EvalRunResponse(BaseModel):
    """Response model for automated evaluation runs."""

    status: str = Field(description="Evaluation run status.")
    mode: str = Field(default="full_agent", description="Evaluation mode.")
    case_count: int = Field(description="Number of evaluated cases.")
    overall_metrics: dict[str, Any] = Field(description="Aggregate evaluation metrics.")
    case_results: list[dict[str, Any]] = Field(description="Per-case evaluation results.")
    gate: dict[str, Any] = Field(default_factory=dict, description="Eval threshold gate result.")
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Machine-readable eval summary.",
    )
    modes: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregate metrics grouped by mode when all_modes is enabled.",
    )
    ablation_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional component ablation summaries.",
    )
    threshold_pass: bool = Field(default=True, description="Whether fail_under threshold passed.")
    trace_stats_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Trace stats snapshot captured after the eval run.",
    )


class EvalRunRequest(BaseModel):
    """Request body for automated evaluation runs."""

    mode: str = Field(default="full_agent", description="Evaluation mode.")
    all_modes: bool = Field(default=False, description="Whether to run all ablation modes.")
    fail_under: float | None = Field(
        default=None,
        description="Optional avg_score threshold for full_agent.",
    )
