"""Knowledge retrieval facade for BusinessInsight Agent."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.rag.index_manager import (
    build_index_manifest,
    filter_allowed_sources,
    index_changed,
    parse_allowed_sources,
    write_index_manifest,
)
from app.rag.loader import load_markdown_documents
from app.rag.splitter import split_documents
from app.rag.vector_store import (
    ChromaVectorStore,
    FaissVectorStore,
    OpenAIEmbeddingVectorStore,
    TfidfVectorStore,
    create_vector_store,
)

VectorStore = TfidfVectorStore | FaissVectorStore | ChromaVectorStore | OpenAIEmbeddingVectorStore


def _load_chunks_and_manifest() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load local docs, split chunks, and build manifest metadata."""

    settings = get_settings()
    documents = load_markdown_documents()
    chunks = split_documents(documents)
    manifest = build_index_manifest(
        documents=documents,
        chunks=chunks,
        backend=settings.rag_backend,
        embedding_provider=settings.rag_embedding_provider,
        embedding_model=settings.rag_embedding_model,
    )
    return chunks, manifest


@lru_cache(maxsize=1)
def _get_vector_store() -> VectorStore:
    """Build and cache the local knowledge index with backend fallback."""

    settings = get_settings()
    backend = settings.rag_backend
    chunks, manifest = _load_chunks_and_manifest()
    write_index_manifest(manifest)
    try:
        return create_vector_store(backend).build_index(chunks)
    except Exception:
        if not settings.rag_embedding_fallback_to_tfidf:
            raise
        return TfidfVectorStore().build_index(chunks)


def refresh_knowledge_index(force: bool = False) -> dict[str, Any]:
    """Refresh the local RAG index only when source content changed or forced."""

    _, manifest = _load_chunks_and_manifest()
    changed = index_changed(manifest)
    if force or changed:
        _get_vector_store.cache_clear()
        _get_vector_store()
    return {
        "refreshed": bool(force or changed),
        "changed": changed,
        "manifest": manifest,
    }


def retrieve_knowledge(
    query: str,
    top_k: int = 5,
    allowed_sources: set[str] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve relevant knowledge chunks with source and score."""

    store = _get_vector_store()
    allowed = set(allowed_sources) if allowed_sources is not None else parse_allowed_sources()
    search_k = top_k if not allowed else max(top_k * 3, top_k)
    results = filter_allowed_sources(store.search(query, top_k=search_k), allowed)
    return [
        {
            "source": result["source"],
            "content": result["content"],
            "score": result["score"],
            "rag_backend": getattr(store, "backend_name", get_settings().rag_backend),
            "embedding_provider": getattr(
                store,
                "embedding_provider",
                get_settings().rag_embedding_provider,
            ),
            "embedding_model": getattr(store, "model", get_settings().rag_embedding_model),
        }
        for result in results[:top_k]
    ]
