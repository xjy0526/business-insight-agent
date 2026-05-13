"""Cache service for Agent API responses with Redis-first fallback."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any
from uuid import uuid4

from app.agent.state import AgentState, _now_iso
from app.config import get_settings
from app.services.trace_service import TraceService

try:  # pragma: no cover - exercised only when redis package and service are available.
    import redis
except ImportError:  # pragma: no cover - local fallback path is covered in tests.
    redis = None  # type: ignore[assignment]


class CacheService:
    """TTL cache with Redis support and safe in-memory fallback."""

    _store: dict[str, tuple[datetime, Any]] = {}
    _lock = RLock()
    _redis_pools: dict[str, Any] = {}
    _redis_pool_lock = RLock()

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        settings = get_settings()
        self.backend = settings.cache_backend.lower()
        self.redis_url = settings.redis_url
        self._redis_client = self._build_redis_client()

    @staticmethod
    def build_key(query: str) -> str:
        """Build a stable, Redis-safe cache key for a user query."""

        digest = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
        return f"agent_analyze:{digest}"

    def get_cache(self, key: str) -> Any | None:
        """Return cached value if it exists and has not expired."""

        if self._redis_client is not None:
            try:
                cached_value = self._redis_client.get(key)
                if cached_value is None:
                    return None
                return json.loads(cached_value)
            except Exception:
                self._redis_client = None

        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None

            expires_at, value = item
            if datetime.now(UTC) >= expires_at:
                self._store.pop(key, None)
                return None

            return deepcopy(value)

    def set_cache(self, key: str, value: Any) -> None:
        """Store a value in cache."""

        if self._redis_client is not None:
            try:
                self._redis_client.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(value, ensure_ascii=False, default=str),
                )
                return
            except Exception:
                self._redis_client = None

        expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
        with self._lock:
            self._store[key] = (expires_at, deepcopy(value))

    def clear_cache(self) -> None:
        """Clear all cached values."""

        if self._redis_client is not None:
            try:
                keys = list(self._redis_client.scan_iter(match="agent_analyze:*"))
                if keys:
                    self._redis_client.delete(*keys)
            except Exception:
                self._redis_client = None

        with self._lock:
            self._store.clear()

    def build_cache_hit_response(
        self,
        query: str,
        key: str,
        cached_payload: dict[str, Any],
        latency_ms: int,
    ) -> dict[str, Any]:
        """Create a request-scoped cache-hit response and persist a lightweight trace."""

        trace_id = str(uuid4())
        payload = deepcopy(cached_payload)
        payload["trace_id"] = trace_id
        payload["cached"] = True
        payload["cache_key"] = key
        payload["latency_ms"] = latency_ms
        payload["answer"] = self._rewrite_answer_trace_id(payload.get("answer", ""), trace_id)

        state = AgentState(
            trace_id=trace_id,
            user_query=query,
            intent=payload.get("intent", ""),
            tool_results=payload.get("tool_results", {}),
            retrieved_docs=payload.get("retrieved_docs", []),
            final_answer=payload.get("answer", ""),
            cache_key=key,
            cache_hit=True,
            finished_at=_now_iso(),
        )
        state.node_spans.append(
            {
                "node": "cache_hit",
                "latency_ms": latency_ms,
                "input_summary": {"cache_key": key},
                "output_summary": {
                    "trace_id": trace_id,
                    "intent": state.intent,
                    "retrieved_docs_count": len(state.retrieved_docs),
                    "tool_result_keys": sorted(state.tool_results.keys()),
                },
                "error_type": None,
            }
        )

        try:
            TraceService().save_trace(state, latency_ms=latency_ms)
        except Exception:
            # Cache hits should remain available even if observability storage is degraded.
            pass

        return payload

    def _build_redis_client(self) -> Any | None:
        """Build a Redis client only when explicitly configured."""

        if self.backend != "redis" or not self.redis_url or redis is None:
            return None

        try:
            pool = self._get_redis_pool(self.redis_url)
            client = redis.Redis(connection_pool=pool)
            client.ping()
            return client
        except Exception:
            return None

    @classmethod
    def _get_redis_pool(cls, redis_url: str) -> Any:
        """Return a shared Redis connection pool for multi-request reuse."""

        if redis is None:
            raise RuntimeError("redis package is unavailable.")

        with cls._redis_pool_lock:
            pool = cls._redis_pools.get(redis_url)
            if pool is None:
                pool = redis.ConnectionPool.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                    max_connections=20,
                )
                cls._redis_pools[redis_url] = pool
            return pool

    @staticmethod
    def _rewrite_answer_trace_id(answer: str, trace_id: str) -> str:
        """Replace or append the trace_id line for a cache-hit response."""

        if "trace_id:" in answer:
            return re.sub(r"(?m)^trace_id:\s*.+$", f"trace_id: {trace_id}", answer)
        return f"{answer}\n\n---\ntrace_id: {trace_id}"
