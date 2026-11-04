"""Application configuration."""

import json
import os
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+asyncpg://localhost/city_doodle"
    database_url_sync: str = "postgresql://localhost/city_doodle"

    # Auth mode. "production" (the default, so a missing AUTH_MODE fails closed)
    # requires a Clerk session JWT as `Authorization: Bearer <jwt>`. "dev" trusts
    # the X-User-Id header and is for local development and tests only: it must
    # be set explicitly and is refused on Fly (see _refuse_dev_auth_on_fly).
    auth_mode: Literal["dev", "production"] = "production"

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

    @model_validator(mode="after")
    def _refuse_dev_auth_on_fly(self):
        """Fail startup rather than trust X-User-Id on a deployed Fly machine."""
        if self.auth_mode == "dev" and os.environ.get("FLY_APP_NAME"):
            raise ValueError(
                "AUTH_MODE=dev trusts the X-User-Id header and is not allowed on Fly "
                "(FLY_APP_NAME is set); use AUTH_MODE=production with Clerk configured"
            )
        return self


settings = Settings()
