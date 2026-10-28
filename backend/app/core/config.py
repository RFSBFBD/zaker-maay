from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Server configuration. Secrets are never returned by the API."""

    app_name: str = "AI Study Platform API"
    app_env: str = "development"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    database_url: str | None = None
    database_url_unpooled: str | None = None
    supabase_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_jwks_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"

    @model_validator(mode="after")
    def populate_supabase_defaults(self) -> "Settings":
        if self.supabase_url:
            base = self.supabase_url.rstrip("/")
            if not self.supabase_jwt_issuer:
                self.supabase_jwt_issuer = f"{base}/auth/v1"
            if not self.supabase_jwt_jwks_url:
                self.supabase_jwt_jwks_url = f"{base}/auth/v1/.well-known/jwks.json"
        if not self.supabase_jwt_audience:
            self.supabase_jwt_audience = "authenticated"
        return self

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
