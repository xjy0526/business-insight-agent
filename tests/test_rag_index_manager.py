"""Tests for RAG source permissions and incremental index manifest."""

from app.config import get_settings
from app.rag.retriever import _get_vector_store, refresh_knowledge_index, retrieve_knowledge


def test_rag_allowed_sources_filter(monkeypatch, tmp_path) -> None:
    """Retriever should enforce source allowlists for permission-aware RAG."""

    monkeypatch.setenv("RAG_ALLOWED_SOURCES", "campaign_rules.md")
    monkeypatch.setenv("RAG_INDEX_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    get_settings.cache_clear()
    _get_vector_store.cache_clear()

    results = retrieve_knowledge("活动参与不足 价格竞争力 满减", top_k=5)

    assert results
    assert {result["source"] for result in results} == {"campaign_rules.md"}
    assert all(result["embedding_provider"] for result in results)


def test_refresh_knowledge_index_writes_manifest(monkeypatch, tmp_path) -> None:
    """Incremental refresh should write a manifest and report refresh status."""

    manifest_path = tmp_path / "knowledge_index_manifest.json"
    monkeypatch.setenv("RAG_INDEX_MANIFEST_PATH", str(manifest_path))
    get_settings.cache_clear()
    _get_vector_store.cache_clear()

    result = refresh_knowledge_index(force=True)

    assert result["refreshed"] is True
    assert result["manifest"]["chunk_count"] > 0
    assert manifest_path.exists()
