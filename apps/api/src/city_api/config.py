"""Application configuration."""

import json

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

    # Auth mode: "dev" trusts the X-User-Id header (local/tests only);
    # "production" requires a Clerk session JWT as `Authorization: Bearer <jwt>`.
    auth_mode: str = "dev"

    # Clerk (CITY-644). CLERK_DOMAIN is the Frontend API hostname from the Clerk
    # dashboard (e.g. "your-app.clerk.accounts.dev"); it is the JWT issuer and
    # serves the JWKS. CLERK_SECRET_KEY is used server-side only, to read a
    # user's primary email (and its verification status) from the Clerk
    # Backend API when linking a first-time Clerk user to an existing account.
    clerk_domain: str = ""
    clerk_secret_key: str = ""
    # Allowed values for the JWT `azp` claim (the origin that minted the
    # token). Empty means "same as CORS": cors_origins + frontend_url, plus
    # Vercel preview deploys matching clerk_authorized_party_regex.
    clerk_authorized_parties: list[str] = []
    clerk_authorized_party_regex: str = (
        r"^https://city-doodle-web-[a-z0-9]+-[a-z0-9]+\.vercel\.app$"
    )

    # CORS configuration
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://city-doodle-web.vercel.app",
    ]

    @field_validator("cors_origins", "clerk_authorized_parties", mode="before")
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
