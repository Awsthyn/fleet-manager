"""Application settings, loaded only from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me"  # noqa: S105 - development placeholder


class Settings(BaseSettings):
    """Runtime configuration.

    Variables not used yet carry development defaults so the app boots locally
    without a .env file. Production refuses the insecure development secret.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: Literal["development", "test", "production"] = "development"

    # Pooled connection URL, used by the application. Defaults to the docker-compose database.
    # Plain libpq URLs as copied from Neon (postgresql://...?sslmode=require) are accepted;
    # see app/db/url.py for how they are adapted to asyncpg.
    DATABASE_URL: str = "postgresql://fleet:fleet@127.0.0.1:5433/fleet"
    # Direct (non-pooled) connection URL, used by Alembic migrations.
    DATABASE_URL_DIRECT: str = "postgresql://fleet:fleet@127.0.0.1:5433/fleet"

    # Comma-separated list in the environment, e.g. "http://localhost:3000,https://example.app".
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    JWT_SECRET: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _reject_dev_secret_in_production(self) -> Self:
        if self.ENV == "production" and self.JWT_SECRET == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set to a real secret when ENV=production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
