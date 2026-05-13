"""Simple character-based text splitter for local knowledge documents."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def split_documents(
    documents: Iterable[dict[str, Any]],
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[dict[str, Any]]:
    """Split documents into overlapping chunks."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0:
        raise ValueError("overlap cannot be negative.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    chunks: list[dict[str, Any]] = []

    for document in documents:
        content = document["content"]
        source = document["source"]
        doc_id = document["doc_id"]
        start = 0
        chunk_index = 0

        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_content = content[start:end].strip()

            if chunk_content:
                chunks.append(
                    {
                        "chunk_id": f"{doc_id}-{chunk_index:03d}",
                        "source": source,
                        "content": chunk_content,
                    }
                )

            if end == len(content):
                break

            start = end - overlap
            chunk_index += 1

    return chunks
