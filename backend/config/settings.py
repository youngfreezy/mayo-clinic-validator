from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import List, Optional


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""

    # Standard Postgres URL (e.g. Neon: postgresql://user:pass@host/db?sslmode=require)
    # If set, takes precedence over PGVECTOR_CONNECTION_STRING.
    DATABASE_URL: Optional[str] = None

    # psycopg3 driver URI used internally by LangChain PGVector
    PGVECTOR_CONNECTION_STRING: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5433/mayo_validation"
    )

    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "mayo-clinic-validator"

    # Allow all origins by default so HF Spaces works without extra config.
    # Override via CORS_ORIGINS env var for stricter deployments.
    CORS_ORIGINS: List[str] = ["*"]

    @model_validator(mode="after")
    def _apply_database_url(self) -> "Settings":
        """Convert a standard postgres:// URL to the postgresql+psycopg:// form."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = "postgresql+psycopg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+psycopg://" + url[len("postgresql://"):]
            self.PGVECTOR_CONNECTION_STRING = url
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# LangSmith reads os.environ directly, not Pydantic. Export so tracing
# activates even when values are only set in .env (not shell env).
import os
os.environ.setdefault("LANGCHAIN_TRACING_V2", settings.LANGCHAIN_TRACING_V2)
os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)
os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)
