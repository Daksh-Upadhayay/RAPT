from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost:5432/rapt"
    test_database_url: str = "postgresql+asyncpg://localhost:5432/rapt_test"

    # Which trained artifact under app/ml/artifacts/<model>/ to serve
    category_model_version: str = "v1"
    urgency_model_version: str = "v4"

    # Knowledge-base (RAG) embeddings. Its output size must equal EMBEDDING_DIM below.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


# Dimension of the knowledge_base.embedding pgvector column (set by its migration).
# Changing the embedding model to one with another size needs a new migration + re-embed.
EMBEDDING_DIM = 384


settings = Settings()
