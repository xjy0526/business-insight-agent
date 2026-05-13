"""Tests for local RAG knowledge retrieval."""

from app.rag import retriever
from app.rag.retriever import retrieve_knowledge
from app.rag.vector_store import TfidfVectorStore, create_vector_store


def _sources(results: list[dict]) -> set[str]:
    """Collect source file names from retrieval results."""

    return {result["source"] for result in results}


def test_refund_logistics_bad_review_query_hits_policy_or_review_guide() -> None:
    """Refund and bad-review query should hit after-sales or review guidance."""

    results = retrieve_knowledge("退款率升高 物流慢 差评", top_k=5)

    assert {"after_sales_policy.md", "review_analysis_guide.md"} & _sources(results)
    assert all("score" in result for result in results)


def test_campaign_competitiveness_query_hits_campaign_rules() -> None:
    """Campaign participation query should hit campaign rules."""

    results = retrieve_knowledge("没有参加平台活动 价格竞争力", top_k=5)

    assert "campaign_rules.md" in _sources(results)


def test_ctr_title_main_image_query_hits_product_operation_guide() -> None:
    """CTR query should hit product operation guidance."""

    results = retrieve_knowledge("点击率下降 主图 标题", top_k=5)

    assert "product_operation_guide.md" in _sources(results)


def test_vector_store_factory_keeps_tfidf_fallback() -> None:
    """The default vector store should remain available without FAISS/Chroma."""

    store = create_vector_store("tfidf")

    assert isinstance(store, TfidfVectorStore)


def test_retriever_falls_back_to_tfidf_when_backend_fails(monkeypatch) -> None:
    """Retriever should keep working when an optional vector backend fails."""

    class BrokenVectorStore:
        def build_index(self, chunks: list[dict]) -> "BrokenVectorStore":
            raise RuntimeError("backend unavailable")

    monkeypatch.setattr(retriever, "create_vector_store", lambda backend: BrokenVectorStore())
    retriever._get_vector_store.cache_clear()

    results = retrieve_knowledge("退款率升高 物流慢 差评", top_k=3)

    assert results
    assert all({"source", "content", "score"}.issubset(result) for result in results)

    retriever._get_vector_store.cache_clear()
