"""Application configuration."""

import json
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+asyncpg://localhost/city_doodle"
    database_url_sync: str = "postgresql://localhost/city_doodle"

    session_expire_days: int = 7

    # Auth mode: "dev" uses X-User-Id header, "production" uses Bearer token
    auth_mode: str = "dev"

    # World Brief (AI terrain prompt, CITY-659). Endpoint returns 503 unless
    # BRIEF_ENABLED=true AND ANTHROPIC_API_KEY is set. BRIEF_ENABLED is the kill switch.
    brief_enabled: bool = False
    anthropic_api_key: str | None = None
    brief_model: str = "claude-opus-5-5"
    brief_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    brief_rate_limit_per_minute: int = 8
    brief_daily_limit_per_user: int = 60
    brief_global_limit_per_minute: int = 60
    # Cross-machine cap (Postgres counter). ~$0.02–0.05 per call at low effort.
    brief_global_daily_limit: int = 500
    brief_max_tokens: int = 4096

    # Logging / Axiom (see city_api.observability). Shipping is off unless
    # AXIOM_API_TOKEN is set; only APP_ENV=production writes to axiom_dataset.
    app_env: str = "development"
    log_level: str = "info"
    axiom_api_token: str | None = None
    axiom_org_id: str | None = None
    axiom_dataset: str = "city-doodle"
    axiom_dataset_dev: str | None = None

    # CORS configuration
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://city-doodle-web.vercel.app",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string (JSON or comma-separated) or list."""
        if isinstance(v, str):
            # Try JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            # Fall back to comma-separated
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
