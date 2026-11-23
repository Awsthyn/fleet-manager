import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import DEV_JWT_SECRET, Settings


class _SettingsWithoutDotenv(Settings):
    """Settings that ignore any local .env file, so tests see only what they set."""

    model_config = Settings.model_config | SettingsConfigDict(env_file=None)


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards CORS_ORIGINS parsing: rejects a single unsplit string or kept blank/padded entries."""
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://fleet.example.app ,")

    settings = _SettingsWithoutDotenv()

    assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://fleet.example.app"]


def test_production_rejects_dev_jwt_secret() -> None:
    """Guards production boot: rejects starting with ENV=production and the dev JWT secret."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _SettingsWithoutDotenv(ENV="production", JWT_SECRET=DEV_JWT_SECRET)


def test_production_accepts_real_jwt_secret() -> None:
    """Guards the production check against overreach: rejects refusing a non-default secret."""
    settings = _SettingsWithoutDotenv(ENV="production", JWT_SECRET="a-real-secret-value")

    assert settings.JWT_SECRET == "a-real-secret-value"
