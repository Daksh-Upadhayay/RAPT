from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The API connects as a restricted role (no superuser, no BYPASSRLS), so Postgres
    # row-level security applies to every query it makes. Migrations, the operator CLI and
    # the seed/ML scripts use the owner connection (admin_*), which bypasses RLS; they
    # filter by tenant themselves. See DECISIONS.md, Phase 7.
    database_url: str = "postgresql+asyncpg://rapt_app@localhost:5432/rapt"
    admin_database_url: str = "postgresql+asyncpg://localhost:5432/rapt"
    test_database_url: str = "postgresql+asyncpg://rapt_app@localhost:5432/rapt_test"
    test_admin_database_url: str = "postgresql+asyncpg://localhost:5432/rapt_test"
    # The restricted role the migrations grant table access to
    app_db_role: str = "rapt_app"

    # Auth: invite-only accounts, a signed JWT in an httpOnly cookie
    jwt_secret: SecretStr | None = None  # required outside tests; see app/core/security.py
    jwt_ttl_hours: int = 12
    cookie_secure: bool = True  # browsers accept Secure cookies on http://localhost
    login_attempts_per_window: int = 10
    login_window_minutes: int = 15

    # Which trained artifact under app/ml/artifacts/<model>/ to serve
    category_model_version: str = "v2"
    urgency_model_version: str = "v4"

    # Knowledge-base (RAG) embeddings. Its output size must equal EMBEDDING_DIM below.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Prepended to search queries only, never to entries: bge was trained with this
    # instruction for query-to-passage retrieval. Set it to "" for a symmetric model.
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "

    # Draft Agent LLM (Phase 8). "auto" builds a fallback chain from the keys that are set:
    # Groq (primary model, then a second model with its own rate limits), Cerebras, then
    # Gemini for the tenants in gemini_allowed_tenants only (its free tier may use prompts
    # for training), then Claude. No key at all: an offline placeholder draft.
    draft_provider: Literal["auto", "groq", "cerebras", "gemini", "claude", "offline"] = "auto"
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str | None = "qwen/qwen3.8-27b"
    cerebras_api_key: SecretStr | None = None
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "gpt-oss-120b"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    # Comma-separated tenant slugs whose tickets may go to Gemini's free tier. Keep this to
    # tenants with synthetic data (dev) or whose owners agreed to it.
    gemini_allowed_tenants: str = "dev"
    anthropic_api_key: SecretStr | None = None
    claude_model: str = "claude-opus-5"
    claude_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_timeout_seconds: float = 45.0
    llm_attempts_per_provider: int = 2  # 429/5xx/timeouts are retried once, then the next provider
    # Rerun tickets a restart left mid-run (app/agents/recovery.py). Single API instance only.
    resume_unfinished_runs_on_startup: bool = True

    # Escalation Agent rules (03-agent-architecture.md)
    escalation_min_confidence: float = 0.6
    refund_escalation_threshold: float = 100.0

    @field_validator("jwt_secret", "groq_api_key", "cerebras_api_key", "gemini_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # Docker Compose passes an unset variable through as "": that means no key, not an
        # empty one (which would build a provider link that fails on every call)
        return None if isinstance(value, str) and not value.strip() else value


# Dimension of the knowledge_base.embedding pgvector column (set by its migration).
# Changing the embedding model to one with another size needs a new migration + re-embed.
EMBEDDING_DIM = 384


settings = Settings()
