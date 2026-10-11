from pathlib import Path
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

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "DATABASE_URL is not set or empty. Please set DATABASE_URL in your backend/.env file."
            )
        return v.strip()

settings = Settings()
