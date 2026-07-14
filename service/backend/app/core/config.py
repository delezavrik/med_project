import json
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_list(value: str | list[str]) -> list[str]:
    """Parse CORS origins from comma-separated or JSON string."""
    if isinstance(value, list):
        return value
    if not value:
        return ["http://localhost:5173"]
    # Try JSON first
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # Parse as comma-separated
    return [item.strip() for item in value.split(",") if item.strip()]


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

    # Store the value - can be string (from env) or list (from code). Converted to string internally.
    cors_allowed_origins: Any = Field(default="http://localhost:5173")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **data):
        # Handle cors_allowed_origins from dict input (for tests and direct code)
        if "cors_allowed_origins" in data:
            value = data["cors_allowed_origins"]
            if isinstance(value, list):
                # Convert list to comma-separated string for storage
                data["cors_allowed_origins"] = ",".join(value)
        super().__init__(**data)

    def __getattribute__(self, name: str):
        """Override to parse cors_allowed_origins as list when accessed."""
        value = object.__getattribute__(self, name)
        if name == "cors_allowed_origins":
            return _parse_cors_list(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
