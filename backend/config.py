import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or a .env file.
    The production deployment should provide a real PostgreSQL DATABASE_URL and a strong JWT secret.
    """
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    CORS_ALLOWED_ORIGINS: str = Field(
        "",
        env="CORS_ALLOWED_ORIGINS",
    )

    # ── Ollama AI Configuration ──────────────────────────────────────────────
    ENABLE_LLM: bool = Field(False, env="ENABLE_LLM")
    OLLAMA_HOST: str = Field("", env="OLLAMA_HOST")
    EMBEDDING_MODEL: str = Field("nomic-embed-text", env="EMBEDDING_MODEL")
    LLM_MODEL: str = Field("llama3.1:8b", env="LLM_MODEL")

    # ── Matching Thresholds ──────────────────────────────────────────────────
    AUTO_MATCH_THRESHOLD: float = Field(0.92, env="AUTO_MATCH_THRESHOLD")
    REVIEW_QUEUE_THRESHOLD: float = Field(0.75, env="REVIEW_QUEUE_THRESHOLD")

    # ── Vector Search ────────────────────────────────────────────────────────
    VECTOR_SEARCH_LIMIT: int = Field(10, env="VECTOR_SEARCH_LIMIT")
    EMBEDDING_BATCH_SIZE: int = Field(64, env="EMBEDDING_BATCH_SIZE")
    EMBEDDING_CONCURRENCY: int = Field(4, env="EMBEDDING_CONCURRENCY")
    CELERY_BROKER_URL: str = Field("redis://redis:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field("redis://redis:6379/1", env="CELERY_RESULT_BACKEND")
    KAFKA_BOOTSTRAP_SERVERS: str = Field("redpanda:9092", env="KAFKA_BOOTSTRAP_SERVERS")

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        env_file_encoding = "utf-8"


settings = Settings()
