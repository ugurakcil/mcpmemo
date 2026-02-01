from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "memory-mcp"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8080

    database_url: str = Field(
        default="postgresql+asyncpg://memory:memory@localhost:5432/memory"
    )
    embedding_dim: int = 1536

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    llm_timeout_s: float = 20.0
    llm_max_retries: int = 3
    llm_circuit_breaker_failures: int = 5
    llm_circuit_breaker_ttl_s: int = 60
    llm_max_concurrency: int = 5

    enable_llm_rerank: bool = False
    fake_llm: bool = False

    vector_index_type: str = "auto"
    vector_ivfflat_lists: int = 100
    vector_hnsw_m: int = 16
    vector_hnsw_ef_construction: int = 128

    dedup_sim_threshold: float = 0.9
    supersede_sim_threshold: float = 0.8
    dedup_llm_guard_min: float = 0.75

    shared_hmac_secret: str = ""
    shared_default_expires_minutes: int = 60

    cache_max_entries: int = 2048
    cache_ttl_s: int = 600

    metrics_enabled: bool = True

    fast_top_k: int = 8
    deep_top_k: int = 20
    token_budget_fast: int = 800
    token_budget_deep: int = 2400

    ingest_embed_sync: bool = False
    auto_distill_on_ingest: bool = False

    job_poll_interval_s: float = 1.0
    job_max_attempts: int = 3

    retention_days_turns: int = 365
    retention_days_memory: int = 3650
    retention_cleanup_interval_s: int = 3600


settings = Settings()
