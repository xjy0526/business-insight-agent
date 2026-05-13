"""Local vector stores with optional FAISS/Chroma and TF-IDF fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


@dataclass
class TfidfVectorStore:
    """A replaceable local retrieval backend for knowledge chunks."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    vectorizer: TfidfVectorizer | None = None
    matrix: Any = None

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


def create_vector_store(
    backend: str = "tfidf",
) -> TfidfVectorStore | FaissVectorStore | ChromaVectorStore:
    """Create the requested vector store and fall back to TF-IDF if unavailable."""

    normalized_backend = backend.lower()
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
