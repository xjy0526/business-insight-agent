"""Application configuration for BusinessInsight Agent."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    app_name: str = "business-insight-agent"
    env: str = "development"
    database_url: str = "sqlite:///./data/business_insight.db"
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "qwen-plus"
    llm_timeout: float = 30.0
    llm_max_retries: int = 2
    llm_fallback_to_mock: bool = True
    llm_timeout_seconds: float | None = Field(default=None, exclude=True)
    cache_backend: str = "memory"
    redis_url: str | None = None
    metrics_backend: str = "sqlite"
    metrics_service_url: str | None = None
    metrics_service_timeout: float = 5.0
    metrics_service_fallback_to_sqlite: bool = True
    rag_backend: str = "tfidf"
    rag_embedding_provider: str = "local_hashing"
    rag_embedding_model: str = "hashing-char-ngram"
    rag_embedding_api_key: str | None = None
    rag_embedding_base_url: str | None = None
    rag_embedding_timeout: float = 30.0
    rag_embedding_fallback_to_tfidf: bool = True
    rag_allowed_sources: str | None = None
    rag_index_manifest_path: str = "./data/knowledge_index_manifest.json"
    agent_runner: str = "sequential"
    langgraph_checkpoint: str = "none"
    langgraph_visual_trace: bool = True
    eval_mode: str = "full_agent"
    eval_min_avg_score: float = 0.72
    eval_min_intent_accuracy: float = 0.7
    eval_golden_answers_path: str = "evals/golden_answers.json"
    eval_history_path: str = "evals/eval_history.jsonl"
    eval_history_report_path: str = "evals/eval_history_report.md"
    trace_alert_p95_latency_ms: int = 1000
    trace_alert_error_rate: float = 0.1
    trace_token_cost_per_1k_input: float = 0.0
    trace_token_cost_per_1k_output: float = 0.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings so the app uses one consistent configuration."""

    return Settings()
