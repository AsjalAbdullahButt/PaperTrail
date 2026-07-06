"""Application configuration.

All settings (DB credentials, OpenAI key, model names) are loaded from
environment variables / the backend/.env file via pydantic-settings so that
no secrets are ever hard-coded. Import the shared ``settings`` instance from
anywhere in the app.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- OpenAI ---
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # --- MySQL ---
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "papertrail"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL pointing at the papertrail database."""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def server_url(self) -> str:
        """SQLAlchemy URL pointing at the MySQL server (no specific database).

        Used once to CREATE DATABASE IF NOT EXISTS before we connect to it.
        """
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/?charset=utf8mb4"
        )

    @property
    def openai_ready(self) -> bool:
        """True when a real-looking OpenAI key is configured."""
        key = self.openai_api_key.strip()
        return key.startswith("sk-") and "your-openai-key" not in key


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
