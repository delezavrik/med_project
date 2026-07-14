from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    cors_allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # Env vars приходят строкой; поддерживаем формат "a,b, c".
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
