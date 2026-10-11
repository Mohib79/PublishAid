import json
from pathlib import Path
from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string with psycopg driver (e.g., postgresql+psycopg://user:pass@host:port/db)",
    )
    TEST_DATABASE_URL: str | None = Field(
        None,
        description="PostgreSQL connection string for tests",
    )
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    # Auth & Security settings
    SECRET_KEY: str = Field(
        ...,
        description="Secret key for signing JWT tokens. Required at startup.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        60,
        description="Lifetime of access tokens in minutes.",
    )
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins list.",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "DATABASE_URL is not set or empty. Please set DATABASE_URL in your backend/.env file."
            )
        return v.strip()

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "SECRET_KEY is not set or empty. Please set SECRET_KEY in your backend/.env file."
            )
        return v.strip()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed]
            except Exception:
                return [orig.strip() for orig in v.split(",") if orig.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v]
        return ["http://localhost:3000"]

settings = Settings()
