from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost:5432/rapt"
    test_database_url: str = "postgresql+asyncpg://localhost:5432/rapt_test"

    # Which trained artifact under app/ml/artifacts/<model>/ to serve
    category_model_version: str = "v1"
    urgency_model_version: str = "v3"


settings = Settings()
