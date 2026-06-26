"""Local vector stores with optional FAISS/Chroma and TF-IDF fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

from app.config import get_settings

try:  # pragma: no cover - import fallback is covered through factory behavior.
    import openai
except ImportError:  # pragma: no cover
    openai = None  # type: ignore[assignment]


DEFAULT_QWEN_EMBEDDING_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
REAL_EMBEDDING_BACKENDS = {"embedding", "openai_embedding", "qwen_embedding"}


@dataclass
class TfidfVectorStore:
    """A replaceable local retrieval backend for knowledge chunks."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    vectorizer: TfidfVectorizer | None = None
    matrix: Any = None
    backend_name: str = "tfidf"
    embedding_provider: str = "local_tfidf"

    def build_index(self, chunks: list[dict[str, Any]]) -> TfidfVectorStore:
        """Build a TF-IDF index from text chunks."""

        self.chunks = chunks
        if not chunks:
            self.vectorizer = None
            self.matrix = None
            return self

        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4))
        self.matrix = self.vectorizer.fit_transform([chunk["content"] for chunk in chunks])
        return self

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the index and return chunks with similarity scores."""

        if top_k <= 0:
            return []
        if self.vectorizer is None or self.matrix is None or not self.chunks:
            return []

        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix).flatten()
        ranked_indices = scores.argsort()[::-1][:top_k]

        results: list[dict[str, Any]] = []
        for index in ranked_indices:
            chunk = self.chunks[int(index)]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "content": chunk["content"],
                    "score": round(float(scores[int(index)]), 6),
                }
            )

        return results


@dataclass
class FaissVectorStore:
    """Optional FAISS backend using local hashing embeddings."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    vectorizer: HashingVectorizer | None = None
    index: Any = None
    backend_name: str = "faiss"
    embedding_provider: str = "local_hashing"

    def build_index(self, chunks: list[dict[str, Any]]) -> FaissVectorStore:
        """Build a FAISS index if faiss is installed, otherwise fail clearly."""

        try:
            import faiss  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError("FAISS backend is unavailable. Install faiss-cpu first.") from error

        self.chunks = chunks
        if not chunks:
            self.vectorizer = None
            self.index = None
            return self

        self.vectorizer = HashingVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            n_features=4096,
            alternate_sign=False,
            norm=None,
        )
        matrix = self.vectorizer.transform([chunk["content"] for chunk in chunks])
        dense_matrix = normalize(matrix).astype("float32").toarray()
        self.index = faiss.IndexFlatIP(dense_matrix.shape[1])
        self.index.add(dense_matrix)
        return self

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the FAISS index and return chunks with similarity scores."""

        if top_k <= 0 or self.vectorizer is None or self.index is None or not self.chunks:
            return []

        query_matrix = self.vectorizer.transform([query])
        query_vector = normalize(query_matrix).astype("float32").toarray()
        scores, indices = self.index.search(query_vector, min(top_k, len(self.chunks)))

        results: list[dict[str, Any]] = []
        for score, index in zip(scores[0], indices[0], strict=False):
            if index < 0:
                continue
            chunk = self.chunks[int(index)]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "content": chunk["content"],
                    "score": round(float(score), 6),
                }
            )
        return results


@dataclass
class ChromaVectorStore:
    """Optional Chroma backend adapter kept behind an import boundary."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    collection: Any = None
    backend_name: str = "chroma"
    embedding_provider: str = "chroma_default"

    def build_index(self, chunks: list[dict[str, Any]]) -> ChromaVectorStore:
        """Build an in-memory Chroma collection when chromadb is installed."""

        try:
            import chromadb  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError("Chroma backend is unavailable. Install chromadb first.") from error

        self.chunks = chunks
        client = chromadb.Client()
        self.collection = client.get_or_create_collection("business_insight_knowledge")
        if chunks:
            self.collection.upsert(
                ids=[chunk["chunk_id"] for chunk in chunks],
                documents=[chunk["content"] for chunk in chunks],
                metadatas=[{"source": chunk["source"]} for chunk in chunks],
            )
        return self

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the Chroma collection and normalize result format."""

        if top_k <= 0 or self.collection is None:
            return []

        raw_results = self.collection.query(query_texts=[query], n_results=top_k)
        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]
        ids = raw_results.get("ids", [[]])[0]

        results: list[dict[str, Any]] = []
        for chunk_id, content, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=False,
        ):
            score = 1.0 / (1.0 + float(distance))
            results.append(
                {
                    "chunk_id": chunk_id,
                    "source": metadata.get("source", ""),
                    "content": content,
                    "score": round(score, 6),
                }
            )
        return results


@dataclass
class OpenAIEmbeddingVectorStore:
    """OpenAI-compatible embedding backend with TF-IDF fallback at caller boundary."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)
    backend_name: str = "embedding"
    embedding_provider: str = "openai_compatible"
    model: str = ""

    def build_index(self, chunks: list[dict[str, Any]]) -> OpenAIEmbeddingVectorStore:
        """Build an in-memory vector index from provider embeddings."""

        settings = get_settings()
        self.chunks = chunks
        self.embedding_provider = settings.rag_embedding_provider
        self.model = settings.rag_embedding_model
        if not chunks:
            self.embeddings = []
            return self
        self.embeddings = self._embed_texts([chunk["content"] for chunk in chunks])
        return self

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search provider embeddings with cosine similarity."""

        if top_k <= 0 or not self.chunks or not self.embeddings:
            return []

        query_embedding = self._embed_texts([query])[0]
        scores = cosine_similarity([query_embedding], self.embeddings).flatten()
        ranked_indices = scores.argsort()[::-1][:top_k]

        results: list[dict[str, Any]] = []
        for index in ranked_indices:
            chunk = self.chunks[int(index)]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "content": chunk["content"],
                    "score": round(float(scores[int(index)]), 6),
                }
            )
        return results

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Call an OpenAI-compatible embeddings endpoint."""

        if openai is None:
            raise RuntimeError("openai package is unavailable for embedding backend.")

        settings = get_settings()
        api_key = settings.rag_embedding_api_key or settings.llm_api_key
        if not api_key:
            raise RuntimeError("RAG embedding API key is not configured.")

        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": settings.rag_embedding_timeout,
            "max_retries": settings.llm_max_retries,
        }
        base_url = _resolve_embedding_base_url(
            provider=settings.rag_embedding_provider,
            configured_base_url=settings.rag_embedding_base_url or settings.llm_base_url,
        )
        if base_url:
            client_kwargs["base_url"] = base_url.rstrip("/")

        client = openai.OpenAI(**client_kwargs)
        response = client.embeddings.create(
            model=settings.rag_embedding_model,
            input=texts,
            timeout=settings.rag_embedding_timeout,
        )
        embeddings = _extract_embedding_vectors(response)
        if len(embeddings) != len(texts):
            raise RuntimeError("Embedding response size does not match input size.")
        return embeddings


def _resolve_embedding_base_url(provider: str, configured_base_url: str | None) -> str | None:
    """Resolve provider-specific default base_url without overriding explicit config."""

    if configured_base_url:
        return configured_base_url
    if provider.lower() in {"qwen", "dashscope"}:
        return DEFAULT_QWEN_EMBEDDING_BASE_URL
    return None


def _extract_embedding_vectors(response: Any) -> list[list[float]]:
    """Read embeddings from SDK or fake-client responses."""

    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data", [])

    vectors: list[list[float]] = []
    for item in data or []:
        vector = getattr(item, "embedding", None)
        if vector is None and isinstance(item, dict):
            vector = item.get("embedding")
        if not isinstance(vector, list):
            raise RuntimeError("Embedding response contains invalid vector data.")
        vectors.append([float(value) for value in vector])
    return vectors


def create_vector_store(
    backend: str = "tfidf",
) -> TfidfVectorStore | FaissVectorStore | ChromaVectorStore | OpenAIEmbeddingVectorStore:
    """Create the requested vector store and fall back to TF-IDF if unavailable."""

    normalized_backend = backend.lower()
    if normalized_backend in REAL_EMBEDDING_BACKENDS:
        return OpenAIEmbeddingVectorStore()
    if normalized_backend == "faiss":
        return FaissVectorStore()
    if normalized_backend == "chroma":
        return ChromaVectorStore()
    return TfidfVectorStore()


_DEFAULT_STORE = TfidfVectorStore()


def build_index(chunks: list[dict[str, Any]]) -> TfidfVectorStore:
    """Build the module-level default TF-IDF index."""

    return _DEFAULT_STORE.build_index(chunks)


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search the module-level default TF-IDF index."""

    return _DEFAULT_STORE.search(query, top_k=top_k)
