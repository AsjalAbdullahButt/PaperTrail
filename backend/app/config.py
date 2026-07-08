"""Application configuration.

All settings (DB credentials, OpenAI key, model names) are loaded from
environment variables / the backend/.env file via pydantic-settings so that
no secrets are ever hard-coded. Import the shared ``settings`` instance from
anywhere in the app.
"""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- OpenAI ---
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # --- Groq (OpenAI-compatible chat API; no embeddings endpoint) ---
    # When set, chat generation (RAG + direct answers) uses Groq via the
    # OpenAI-compatible client. Groq has no embeddings API, so embeddings still
    # come from the offline hasher unless a real OpenAI key is also configured.
    groq_api_key: str = ""
    groq_chat_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # --- MySQL ---
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "papertrail"

    # --- Uploads / limits ---
    # Hard ceiling on a single upload. Rejected with HTTP 413 above this.
    max_upload_mb: int = 50
    # Directory (outside the web root) where original uploads are stored as
    # uploads/{user_id}/{uuid}.{ext}. Never inside frontend/public.
    uploads_dir: str = "uploads"
    # When false, the original file is deleted after processing (only chunks +
    # embeddings are needed to answer queries).
    store_originals: bool = True
    # Hard ceiling on how many chunks a single RAG query will scan in memory.
    # NOTE: brute-force NumPy cosine similarity does not scale past a few
    # thousand chunks; beyond this a real ANN/vector index is required.
    max_query_chunks: int = 5000

    # --- CORS ---
    # Comma-separated list of allowed browser origins. Environment-driven so
    # production origins are configured without code changes.
    cors_origins: str = "http://localhost:3000"

    # --- Auth (JWT) ---
    # Secret used to sign JWTs. MUST be overridden in production via env;
    # the dev default is deliberately obvious and unsafe.
    jwt_secret: str = "dev-only-insecure-change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30  # short-lived access tokens (Phase 1)
    # Refresh tokens are long-lived and stored in an httpOnly cookie; a new
    # access token is minted from them without re-entering credentials.
    refresh_expire_days: int = 7
    # Name of the httpOnly cookie carrying the refresh token.
    refresh_cookie_name: str = "papertrail_refresh"
    # Secure flag on the refresh cookie. Off in local dev (http), on in prod.
    cookie_secure: bool = False

    # --- Redis / rate limiting / caching ---
    # When set (e.g. redis://localhost:6379/0) rate limiting and the query cache
    # use Redis so limits/cache are shared across API workers. When empty they
    # fall back to in-process storage (fine for a single worker / local dev).
    redis_url: str = ""
    rate_limit_enabled: bool = True
    rate_limit_query: str = "60/minute"
    rate_limit_upload: str = "20/minute"
    # Query-response cache TTL in seconds (0 disables caching).
    query_cache_ttl_seconds: int = 300

    # --- SQLAlchemy connection pool ---
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800  # recycle connections every 30 min

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL pointing at the papertrail database.

        Credentials are percent-encoded so passwords containing '@', ':', '/',
        '#', etc. don't corrupt the URL.
        """
        user = quote_plus(self.db_user)
        pwd = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def server_url(self) -> str:
        """SQLAlchemy URL pointing at the MySQL server (no specific database).

        Used once to CREATE DATABASE IF NOT EXISTS before we connect to it.
        """
        user = quote_plus(self.db_user)
        pwd = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parsed allow-list of CORS origins (empty entries dropped)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def jwt_secret_is_default(self) -> bool:
        return self.jwt_secret == "dev-only-insecure-change-me-in-production-please"

    @property
    def openai_ready(self) -> bool:
        """True when a real-looking OpenAI key is configured."""
        key = self.openai_api_key.strip()
        return key.startswith("sk-") and "your-openai-key" not in key

    @property
    def groq_ready(self) -> bool:
        """True when a real-looking Groq key is configured."""
        return self.groq_api_key.strip().startswith("gsk_")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
