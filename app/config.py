"""Application configuration for BusinessInsight Agent."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    app_name: str = "business-insight-agent"
    env: str = "development"
    database_url: str = "sqlite:///./data/business_insight.db"
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    cache_backend: str = "memory"
    redis_url: str | None = None
    rag_backend: str = "tfidf"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings so the app uses one consistent configuration."""

    return Settings()
