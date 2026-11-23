import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import verify_password
from app.models import User, UserRole
from app.scripts.seed import (
    DEMO_EMAIL,
    MissingSeedSettingsError,
    SeedUser,
    seed_users,
    seed_users_from_settings,
)

USERS = [
    SeedUser(email=DEMO_EMAIL, password="demo-pass-123", role=UserRole.VIEWER),
    SeedUser(email="Admin@Fleet.Test", password="admin-pass-456", role=UserRole.ADMIN),
]


async def _users(session: AsyncSession) -> dict[str, User]:
    return {u.email: u for u in (await session.scalars(select(User))).all()}


async def test_seed_users_creates_demo_viewer_and_admin_with_hashed_passwords(
    db_session: AsyncSession,
) -> None:
    """Guards seed users: rejects plaintext passwords, wrong roles or unnormalized emails."""
    created, updated = await seed_users(db_session, USERS)
    users = await _users(db_session)

    assert (created, updated) == (2, 0)
    assert users[DEMO_EMAIL].role is UserRole.VIEWER
    assert users["admin@fleet.test"].role is UserRole.ADMIN
    assert users[DEMO_EMAIL].hashed_password != "demo-pass-123"
    assert verify_password("demo-pass-123", users[DEMO_EMAIL].hashed_password)


async def test_seed_users_is_idempotent_and_applies_password_changes(
    db_session: AsyncSession,
) -> None:
    """Guards re-seeding: rejects duplicate users or ignoring a changed password."""
    await seed_users(db_session, USERS)

    second = await seed_users(db_session, USERS)
    changed = await seed_users(
        db_session, [SeedUser(DEMO_EMAIL, "new-demo-pass-789", UserRole.VIEWER)]
    )
    users = await _users(db_session)

    assert second == (0, 0)
    assert changed == (0, 1)
    assert len(users) == 2
    assert verify_password("new-demo-pass-789", users[DEMO_EMAIL].hashed_password)


def test_seed_users_require_environment_variables() -> None:
    """Guards secret handling: rejects seeding users without passwords from the environment."""
    settings = Settings(ENV="test", DEMO_PASSWORD=None, ADMIN_EMAIL=None, ADMIN_PASSWORD=None)

    with pytest.raises(MissingSeedSettingsError) as error:
        seed_users_from_settings(settings)

    for variable in ("DEMO_PASSWORD", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
        assert variable in str(error.value)


def test_seed_users_from_settings_builds_viewer_and_admin() -> None:
    """Guards role assignment: rejects the demo user getting admin rights or vice versa."""
    settings = Settings(
        ENV="test",
        DEMO_PASSWORD=SecretStr("demo-pass-123"),
        ADMIN_EMAIL=" Boss@Fleet.Test ",
        ADMIN_PASSWORD=SecretStr("admin-pass-456"),
    )

    users = seed_users_from_settings(settings)

    assert [(u.email, u.role) for u in users] == [
        (DEMO_EMAIL, UserRole.VIEWER),
        ("boss@fleet.test", UserRole.ADMIN),
    ]
