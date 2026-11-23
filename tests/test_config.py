import pytest
from pydantic import SecretStr, ValidationError
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


def test_port_comes_from_env_with_8000_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards the listening port: rejects ignoring Render's PORT, a wrong default, or port 0."""
    assert _SettingsWithoutDotenv().PORT == 8000

    monkeypatch.setenv("PORT", "10000")
    assert _SettingsWithoutDotenv().PORT == 10000

    monkeypatch.setenv("PORT", "0")
    with pytest.raises(ValidationError, match="PORT"):
        _SettingsWithoutDotenv()


def test_production_rejects_dev_jwt_secret() -> None:
    """Guards production boot: rejects starting with ENV=production and the dev JWT secret."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _SettingsWithoutDotenv(ENV="production", JWT_SECRET=DEV_JWT_SECRET)


def test_production_accepts_real_jwt_secret() -> None:
    """Guards the production check against overreach: rejects refusing a non-default secret."""
    settings = _SettingsWithoutDotenv(ENV="production", JWT_SECRET="a-real-secret-value")

    assert settings.JWT_SECRET == "a-real-secret-value"


def test_settings_errors_never_echo_secret_values() -> None:
    """Guards startup logs: rejects validation errors that print database URLs or passwords."""
    with pytest.raises(ValidationError) as error:
        _SettingsWithoutDotenv(
            ENV="production",
            JWT_SECRET=DEV_JWT_SECRET,
            DATABASE_URL="postgresql://user:db-secret-123@host/db",
            ADMIN_PASSWORD=SecretStr("admin-secret-456"),
        )

    message = str(error.value)
    assert "JWT_SECRET must be set" in message
    assert "db-secret-123" not in message
    assert "admin-secret-456" not in message
