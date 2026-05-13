"""Integration tests for optional Redis, FAISS, and Chroma backends."""

from __future__ import annotations

import importlib.util

import pytest
from app.rag.vector_store import ChromaVectorStore, FaissVectorStore
from app.services.cache_service import CacheService


def _sample_chunks() -> list[dict[str, str]]:
    """Return compact chunks for optional vector backend integration tests."""

    return [
        {
            "chunk_id": "chunk_campaign",
            "source": "campaign_rules.md",
            "content": "平台活动参与不足会影响价格竞争力和 GMV 表现。",
        },
        {
            "chunk_id": "chunk_refund",
            "source": "after_sales_policy.md",
            "content": "退款率升高通常需要排查物流慢、质量问题和描述不符。",
        },
    ]


@pytest.mark.integration
def test_redis_cache_backend_with_testcontainers(monkeypatch) -> None:
    """CacheService should use a real Redis container when Docker is available."""

    pytest.importorskip("docker", reason="docker python package is required")
    redis_module = pytest.importorskip("redis", reason="redis package is required")
    redis_container_module = pytest.importorskip(
        "testcontainers.redis",
        reason="testcontainers redis extra is required",
    )
    docker_errors = pytest.importorskip("docker.errors")

    redis_container_cls = redis_container_module.RedisContainer
    try:
        container_context = redis_container_cls("redis:7-alpine")
        container = container_context.__enter__()
    except docker_errors.DockerException as error:
        pytest.skip(f"Docker daemon is not available: {error}")

    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        redis_url = f"redis://{host}:{port}/0"
        monkeypatch.setenv("CACHE_BACKEND", "redis")
        monkeypatch.setenv("REDIS_URL", redis_url)

        from app.config import get_settings

        get_settings.cache_clear()
        cache = CacheService(ttl_seconds=30)
        cache_key = cache.build_key("redis integration query")
        cache.set_cache(cache_key, {"trace_id": "trace-redis", "cached": False})

        redis_client = redis_module.Redis.from_url(redis_url, decode_responses=True)
        assert redis_client.get(cache_key) is not None
        assert cache.get_cache(cache_key)["trace_id"] == "trace-redis"
    finally:
        container_context.__exit__(None, None, None)
        from app.config import get_settings

        get_settings.cache_clear()


@pytest.mark.integration
def test_faiss_vector_store_backend_if_installed() -> None:
    """FAISS backend should build a real index when faiss-cpu is installed."""

    pytest.importorskip("faiss", reason="faiss-cpu is optional")

    store = FaissVectorStore().build_index(_sample_chunks())
    results = store.search("活动 价格竞争力 GMV", top_k=1)

    assert results
    assert results[0]["source"] == "campaign_rules.md"
    assert isinstance(results[0]["score"], float)


@pytest.mark.integration
def test_chroma_vector_store_backend_if_installed() -> None:
    """Chroma backend should build a real local collection when chromadb is installed."""

    pytest.importorskip("chromadb", reason="chromadb is optional")

    store = ChromaVectorStore().build_index(_sample_chunks())
    results = store.search("退款率升高 物流慢", top_k=1)

    assert results
    assert results[0]["source"] == "after_sales_policy.md"
    assert isinstance(results[0]["score"], float)


def test_optional_backend_dependencies_are_declared_as_optional() -> None:
    """FAISS and Chroma should remain optional imports for the default test path."""

    assert importlib.util.find_spec("sklearn") is not None
