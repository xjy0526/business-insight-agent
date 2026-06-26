"""Tool wrapper for searching local business knowledge."""

from __future__ import annotations

from typing import Any

from app.rag.retriever import retrieve_knowledge
from app.services.security_service import SecurityService


def _build_evidence_summary(results: list[dict[str, Any]]) -> str:
    """Create a compact evidence summary from retrieval results."""

    if not results:
        return "未检索到相关业务知识证据。"

    summary_items = []
    for index, result in enumerate(results, start=1):
        content = result.get("sanitized_content", result["content"]).replace("\n", " ")
        snippet = content[:120] + ("..." if len(content) > 120 else "")
        summary_items.append(f"{index}. {result['source']} score={result['score']}: {snippet}")

    high_risk_count = sum(
        1 for result in results if result.get("security_risk_level") == "high"
    )
    if high_risk_count:
        summary_items.append(
            "安全提示：部分检索内容存在潜在 Prompt Injection 风险，已做清洗处理。"
        )

    return "\n".join(summary_items)


def _sanitize_retrieval_result(
    result: dict[str, Any],
    security: SecurityService,
) -> dict[str, Any]:
    """Attach security metadata and sanitized content to one retrieval result."""

    content = str(result.get("content", ""))
    detection = security.detect_prompt_injection(content)
    sanitized_content = (
        str(detection["sanitized_text"]) if detection["is_injection"] else content
    )
    sanitized_result = {**result}
    sanitized_result["content"] = sanitized_content
    sanitized_result["sanitized_content"] = sanitized_content
    sanitized_result["security_risk_level"] = detection["risk_level"]
    sanitized_result["injection_patterns"] = detection["matched_patterns"]
    return sanitized_result


def search_business_knowledge(
    query: str,
    allowed_sources: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Search local business knowledge and return evidence for agent reports."""

    security = SecurityService()
    if allowed_sources is None:
        retrieved_results = retrieve_knowledge(query, top_k=5)
    else:
        retrieved_results = retrieve_knowledge(
            query,
            top_k=5,
            allowed_sources=allowed_sources,
        )
    results = [
        _sanitize_retrieval_result(result, security)
        for result in retrieved_results
    ]
    risk_levels = [str(result["security_risk_level"]) for result in results]
    return {
        "query": query,
        "results": results,
        "evidence_summary": _build_evidence_summary(results),
        "security_summary": {
            "high_risk_count": risk_levels.count("high"),
            "medium_risk_count": risk_levels.count("medium"),
            "sanitized": any(level in {"medium", "high"} for level in risk_levels),
        },
    }
