"""Worker configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Worker settings loaded from environment variables."""

    database_url: str = "postgresql+asyncpg://localhost/city_doodle"

    # Worker configuration
    poll_interval_seconds: float = 1.0
    max_poll_interval_seconds: float = 30.0
    max_concurrent_jobs: int = 2
    job_timeout_seconds: int = 300

    # LISTEN/NOTIFY configuration
    # Fallback poll interval when using LISTEN/NOTIFY (safety-net only).
    listen_timeout_seconds: float = 60.0
    # Direct (non-pooled) connection for LISTEN (CITY-701). PgBouncer in
    # transaction mode, e.g. Neon's "-pooler" endpoint, silently drops LISTEN.
    # When unset, DATABASE_URL is used with "-pooler" stripped from a Neon host.
    listen_database_url: str | None = None

    # Logging
    log_level: str = "info"

    # Axiom log shipping (see city_worker.observability). Off unless AXIOM_API_TOKEN
    # is set; only APP_ENV=production writes to axiom_dataset.
    app_env: str = "development"
    axiom_api_token: str | None = None
    axiom_org_id: str | None = None
    axiom_dataset: str = "city-doodle"
    axiom_dataset_dev: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
