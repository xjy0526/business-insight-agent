"""Tool wrapper for searching local business knowledge."""

from __future__ import annotations

from typing import Any

from app.rag.retriever import retrieve_knowledge


def _build_evidence_summary(results: list[dict[str, Any]]) -> str:
    """Create a compact evidence summary from retrieval results."""

    if not results:
        return "未检索到相关业务知识证据。"

    summary_items = []
    for index, result in enumerate(results, start=1):
        content = result["content"].replace("\n", " ")
        snippet = content[:120] + ("..." if len(content) > 120 else "")
        summary_items.append(f"{index}. {result['source']} score={result['score']}: {snippet}")

    return "\n".join(summary_items)


def search_business_knowledge(query: str) -> dict[str, Any]:
    """Search local business knowledge and return evidence for agent reports."""

    results = retrieve_knowledge(query, top_k=5)
    return {
        "query": query,
        "results": results,
        "evidence_summary": _build_evidence_summary(results),
    }
