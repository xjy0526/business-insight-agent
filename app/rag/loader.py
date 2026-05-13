"""Load local Markdown knowledge documents for RAG retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge_docs"


def load_markdown_documents(docs_dir: str | Path = DEFAULT_KNOWLEDGE_DIR) -> list[dict[str, Any]]:
    """Read Markdown documents and return doc_id, source, and content."""

    knowledge_dir = Path(docs_dir)
    documents: list[dict[str, Any]] = []

    for markdown_path in sorted(knowledge_dir.glob("*.md")):
        if markdown_path.name.lower() == "readme.md":
            continue

        content = markdown_path.read_text(encoding="utf-8").strip()
        if not content:
            continue

        documents.append(
            {
                "doc_id": markdown_path.stem,
                "source": markdown_path.name,
                "content": content,
            }
        )

    return documents
