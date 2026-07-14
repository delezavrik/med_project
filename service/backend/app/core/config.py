from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Reviews Analytics Service"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    postgres_dsn: str | None = None
    postgres_pool_min_size: int = 2
    postgres_pool_max_size: int = 10
    postgres_pool_timeout: float = 30.0

    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "reviews_embeddings"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5"
    embedding_model_name: str = "BAAI/bge-m3"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
