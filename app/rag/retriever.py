"""Knowledge retrieval facade for BusinessInsight Agent."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.rag.loader import load_markdown_documents
from app.rag.splitter import split_documents
from app.rag.vector_store import (
    ChromaVectorStore,
    FaissVectorStore,
    TfidfVectorStore,
    create_vector_store,
)

VectorStore = TfidfVectorStore | FaissVectorStore | ChromaVectorStore


@lru_cache(maxsize=1)
def _get_vector_store() -> VectorStore:
    """Build and cache the local knowledge index with backend fallback."""

    documents = load_markdown_documents()
    chunks = split_documents(documents)
    backend = get_settings().rag_backend
    try:
        return create_vector_store(backend).build_index(chunks)
    except Exception:
        return TfidfVectorStore().build_index(chunks)


def retrieve_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve relevant knowledge chunks with source and score."""

    store = _get_vector_store()
    results = store.search(query, top_k=top_k)
    return [
        {
            "source": result["source"],
            "content": result["content"],
            "score": result["score"],
        }
        for result in results
    ]
