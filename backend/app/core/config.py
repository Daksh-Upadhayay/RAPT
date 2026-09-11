from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost:5432/rapt"
    test_database_url: str = "postgresql+asyncpg://localhost:5432/rapt_test"

    # Which trained artifact under app/ml/artifacts/<model>/ to serve
    category_model_version: str = "v1"
    urgency_model_version: str = "v4"

    # Knowledge-base (RAG) embeddings. Its output size must equal EMBEDDING_DIM below.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Prepended to search queries only, never to entries: bge was trained with this
    # instruction for query-to-passage retrieval. Set it to "" for a symmetric model.
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "

    # Draft Agent LLM. "auto" = Gemini if GEMINI_API_KEY is set, else Claude if
    # ANTHROPIC_API_KEY is set, else an offline placeholder draft.
    draft_provider: Literal["auto", "gemini", "claude", "offline"] = "auto"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    anthropic_api_key: SecretStr | None = None
    claude_model: str = "claude-opus-5"
    claude_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"

    # Escalation Agent rules (03-agent-architecture.md)
    escalation_min_confidence: float = 0.6
    refund_escalation_threshold: float = 100.0


# Dimension of the knowledge_base.embedding pgvector column (set by its migration).
# Changing the embedding model to one with another size needs a new migration + re-embed.
EMBEDDING_DIM = 384


settings = Settings()
