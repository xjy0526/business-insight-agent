"""Index metadata, source filtering, and incremental refresh helpers for RAG."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings


def parse_allowed_sources(value: str | None = None) -> set[str] | None:
    """Parse comma-separated source allowlist from config or caller input."""

    raw_value = value if value is not None else get_settings().rag_allowed_sources
    if not raw_value:
        return None
    allowed_sources = {source.strip() for source in raw_value.split(",") if source.strip()}
    return allowed_sources or None


def filter_allowed_sources(
    results: list[dict[str, Any]],
    allowed_sources: set[str] | None,
) -> list[dict[str, Any]]:
    """Filter retrieval results by source-level permissions."""

    if not allowed_sources:
        return results
    return [result for result in results if result.get("source") in allowed_sources]


def build_index_manifest(
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    backend: str,
    embedding_provider: str,
    embedding_model: str,
) -> dict[str, Any]:
    """Build a lightweight manifest for incremental index refresh checks."""

    chunk_counts: dict[str, int] = {}
    for chunk in chunks:
        source = str(chunk.get("source", ""))
        chunk_counts[source] = chunk_counts.get(source, 0) + 1

    sources = []
    for document in documents:
        content = str(document.get("content", ""))
        source = str(document.get("source", ""))
        sources.append(
            {
                "source": source,
                "doc_id": document.get("doc_id"),
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "char_count": len(content),
                "chunk_count": chunk_counts.get(source, 0),
            }
        )

    fingerprint_input = json.dumps(sources, ensure_ascii=False, sort_keys=True)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "backend": backend,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "sources": sources,
        "fingerprint": hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
    }


def load_index_manifest(path: str | Path | None = None) -> dict[str, Any] | None:
    """Load an existing index manifest if it is present and valid."""

    manifest_path = Path(path or get_settings().rag_index_manifest_path)
    if not manifest_path.exists():
        return None
    try:
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def write_index_manifest(manifest: dict[str, Any], path: str | Path | None = None) -> None:
    """Persist the current index manifest for later incremental checks."""

    manifest_path = Path(path or get_settings().rag_index_manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def index_changed(manifest: dict[str, Any], path: str | Path | None = None) -> bool:
    """Return whether the current manifest differs from the persisted manifest."""

    previous = load_index_manifest(path)
    if previous is None:
        return True
    return previous.get("fingerprint") != manifest.get("fingerprint")
