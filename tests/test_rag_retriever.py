"""Tests for local RAG knowledge retrieval."""

from types import SimpleNamespace

from app.config import get_settings
from app.rag import retriever, vector_store
from app.rag.retriever import retrieve_knowledge
from app.rag.vector_store import (
    OpenAIEmbeddingVectorStore,
    TfidfVectorStore,
    create_vector_store,
)


def _sources(results: list[dict]) -> set[str]:
    """Collect source file names from retrieval results."""

    return {result["source"] for result in results}


def test_refund_service_bad_review_query_hits_policy_or_review_guide() -> None:
    """Refund and bad-review query should hit after-sales or review guidance."""

    results = retrieve_knowledge("退款率升高 等待时间长 差评", top_k=5)

    assert {"after_sales_policy.md", "review_analysis_guide.md"} & _sources(results)
    assert all("score" in result for result in results)


def test_campaign_competitiveness_query_hits_campaign_rules() -> None:
    """Campaign participation query should hit campaign rules."""

    results = retrieve_knowledge("没有参加平台活动 价格竞争力", top_k=5)

    assert "campaign_rules.md" in _sources(results)


def test_ctr_title_main_image_query_hits_product_operation_guide() -> None:
    """CTR query should hit product operation guidance."""

    results = retrieve_knowledge("点击率下降 项目图 标题", top_k=5)

    assert "product_operation_guide.md" in _sources(results)


def test_vector_store_factory_keeps_tfidf_fallback() -> None:
    """The default vector store should remain available without FAISS/Chroma."""

    store = create_vector_store("tfidf")

    assert isinstance(store, TfidfVectorStore)


def test_openai_compatible_embedding_store_uses_fake_client(monkeypatch) -> None:
    """Real embedding backend should be testable without network calls."""

    captured: dict[str, object] = {}

    class FakeEmbeddings:
        def create(self, model: str, input: list[str], timeout: float) -> SimpleNamespace:
            captured["model"] = model
            captured["timeout"] = timeout
            vectors = []
            for text in input:
                vectors.append([1.0, 0.0] if "alpha" in text else [0.0, 1.0])
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=vector) for vector in vectors]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs
            self.embeddings = FakeEmbeddings()

    monkeypatch.setenv("RAG_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "text-embedding-test")
    get_settings.cache_clear()
    monkeypatch.setattr(vector_store, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    store = create_vector_store("embedding").build_index(
        [
            {"chunk_id": "a", "source": "alpha.md", "content": "alpha refund policy"},
            {"chunk_id": "b", "source": "beta.md", "content": "beta campaign guide"},
        ]
    )
    results = store.search("alpha issue", top_k=1)

    assert isinstance(store, OpenAIEmbeddingVectorStore)
    assert results[0]["source"] == "alpha.md"
    assert captured["model"] == "text-embedding-test"
    client_kwargs = captured["client_kwargs"]
    assert isinstance(client_kwargs, dict)
    assert "api_key" in client_kwargs


def test_embedding_backend_falls_back_to_tfidf_without_key(monkeypatch) -> None:
    """Missing embedding credentials should not break local RAG."""

    monkeypatch.setenv("RAG_BACKEND", "embedding")
    monkeypatch.delenv("RAG_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()
    retriever._get_vector_store.cache_clear()

    results = retrieve_knowledge("退款率升高 等待时间长 差评", top_k=3)

    assert results
    assert all(result["rag_backend"] == "tfidf" for result in results)

    retriever._get_vector_store.cache_clear()
    get_settings.cache_clear()


def test_retriever_falls_back_to_tfidf_when_backend_fails(monkeypatch) -> None:
    """Retriever should keep working when an optional vector backend fails."""

    class BrokenVectorStore:
        def build_index(self, chunks: list[dict]) -> "BrokenVectorStore":
            raise RuntimeError("backend unavailable")

    monkeypatch.setattr(retriever, "create_vector_store", lambda backend: BrokenVectorStore())
    retriever._get_vector_store.cache_clear()

    results = retrieve_knowledge("退款率升高 等待时间长 差评", top_k=3)

    assert results
    assert all({"source", "content", "score"}.issubset(result) for result in results)

    retriever._get_vector_store.cache_clear()
