from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "AgentStack"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql://agentstack:agentstack@localhost:5432/agentstack"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    embedding_provider: str = "local"  # "local" (sentence-transformers) or "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 384

    so_api_key: str = ""
    github_token: str = ""

    api_key_header: str = "X-API-Key"

    redis_cache_ttl: int = 3600
    search_similarity_threshold: float = 0.35
    max_search_results: int = 10

    class Config:
        env_file = ".env"
        env_prefix = "AGENTSTACK_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
