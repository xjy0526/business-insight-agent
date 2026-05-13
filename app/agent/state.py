"""Shared state model for the BusinessInsight Agent state machine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


class AgentState(BaseModel):
    """State passed between agent nodes."""

    trace_id: str
    user_query: str
    intent: str = ""
    entity_type: str = ""
    entity_id: str = ""
    related_entity_ids: list[str] = Field(default_factory=list)
    metric: str = ""
    time_range: dict[str, Any] = Field(default_factory=dict)
    plan_steps: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    retrieved_docs: list[dict[str, Any]] = Field(default_factory=list)
    diagnosis: str = ""
    reflection_result: dict[str, Any] = Field(default_factory=dict)
    final_answer: str = ""
    errors: list[dict[str, str]] = Field(default_factory=list)
    node_spans: list[dict[str, Any]] = Field(default_factory=list)
    cache_key: str | None = None
    cache_hit: bool = False
    started_at: str = Field(default_factory=_now_iso)
    finished_at: str | None = None
