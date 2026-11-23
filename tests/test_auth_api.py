import re
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_token, hash_password
from app.main import create_app
from app.models import User, UserRole
from tests.conftest import isolated_settings

LOGIN = "/api/v1/auth/login"
PASSWORD = "correct-horse-battery"


async def make_user(
    db_session: AsyncSession,
    email: str = "viewer@fleet.test",
    role: UserRole = UserRole.VIEWER,
    is_active: bool = True,
) -> User:
    user = User(
        email=email, hashed_password=hash_password(PASSWORD), role=role, is_active=is_active
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> Response:
    return await client.post(LOGIN, data={"username": email, "password": password})


async def bearer(client: AsyncClient, email: str) -> dict[str, str]:
    response = await login(client, email)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_login_returns_token_pair_usable_on_me(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards login: rejects missing tokens, wrong lifetimes or /me leaking the password hash."""
    await make_user(db_session, email="viewer@fleet.test")

    response = await login(anonymous_client, "  Viewer@Fleet.TEST ")
    tokens = response.json()
    me = await anonymous_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 200
    assert tokens["token_type"] == "bearer"
    assert (tokens["expires_in"], tokens["refresh_expires_in"]) == (15 * 60, 7 * 24 * 3600)
    assert tokens["refresh_token"] != tokens["access_token"]
    assert me.status_code == 200
    assert set(me.json()) == {"id", "email", "role", "is_active", "created_at"}
    assert (me.json()["email"], me.json()["role"]) == ("viewer@fleet.test", "viewer")


@pytest.mark.parametrize(
    ("email", "password", "is_active"),
    [
        ("viewer@fleet.test", "wrong-password", True),
        ("nobody@fleet.test", PASSWORD, True),
        ("viewer@fleet.test", PASSWORD, False),
    ],
    ids=["wrong-password", "unknown-email", "inactive-user"],
)
async def test_failed_login_returns_401_without_revealing_why(
    anonymous_client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    password: str,
    is_active: bool,
) -> None:
    """Guards login failures: rejects a token, or messages that reveal which accounts exist."""
    await make_user(db_session, email="viewer@fleet.test", is_active=is_active)

    response = await login(anonymous_client, email, password)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"] == {
        "code": "unauthorized",
        "message": "Incorrect email or password",
        "details": None,
    }


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/vehicles"),
        ("GET", "/api/v1/vehicles/1"),
        ("POST", "/api/v1/vehicles"),
        ("GET", "/api/v1/drivers"),
        ("DELETE", "/api/v1/drivers/1"),
        ("GET", "/api/v1/maintenance-records"),
        ("PATCH", "/api/v1/fuel-logs/1"),
        ("GET", "/api/v1/auth/me"),
    ],
)
async def test_protected_endpoints_return_401_without_token(
    anonymous_client: AsyncClient, method: str, path: str
) -> None:
    """Guards authentication: rejects serving or validating any /api/v1 resource without a token."""
    response = await anonymous_client.request(method, path, json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json"])
async def test_public_endpoints_need_no_token(anonymous_client: AsyncClient, path: str) -> None:
    """Guards the public surface: rejects requiring a token for health, docs or the schema."""
    response = await anonymous_client.get(path)

    assert response.status_code == 200


async def test_expired_access_token_is_rejected(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards token expiry: rejects an access token used after its 15-minute lifetime."""
    user = await make_user(db_session)
    issued_long_ago = datetime.now(UTC) - timedelta(minutes=16)
    expired = create_token(user.id, "access", isolated_settings(), now=issued_long_ago)

    response = await anonymous_client.get(
        "/api/v1/vehicles", headers={"Authorization": f"Bearer {expired.token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Token has expired"


async def test_token_signed_with_another_secret_is_rejected(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards signature checks: rejects a well-formed token signed with a different secret."""
    user = await make_user(db_session)
    forged = create_token(
        user.id, "access", isolated_settings(JWT_SECRET="attacker-secret-with-at-least-32-bytes")
    )

    response = await anonymous_client.get(
        "/api/v1/vehicles", headers={"Authorization": f"Bearer {forged.token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid token"


async def test_refresh_issues_a_working_access_token(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards POST /auth/refresh: rejects a refresh that fails or returns an unusable token."""
    await make_user(db_session)
    tokens = (await login(anonymous_client, "viewer@fleet.test")).json()

    refreshed = await anonymous_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    me = await anonymous_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["expires_in"] == 15 * 60
    assert me.status_code == 200


async def test_token_types_are_not_interchangeable(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards token types: rejects a refresh token as bearer and an access token for refresh."""
    await make_user(db_session)
    tokens = (await login(anonymous_client, "viewer@fleet.test")).json()

    refresh_as_bearer = await anonymous_client.get(
        "/api/v1/vehicles", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    access_as_refresh = await anonymous_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert refresh_as_bearer.status_code == 401
    assert access_as_refresh.status_code == 401
    assert access_as_refresh.json()["error"]["message"] == "Invalid token type"


async def test_deactivated_user_tokens_stop_working(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards revocation by deactivation: rejects outstanding tokens of a now-inactive user."""
    user = await make_user(db_session)
    tokens = (await login(anonymous_client, user.email)).json()
    user.is_active = False
    await db_session.flush()

    access = await anonymous_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    refresh = await anonymous_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert (access.status_code, refresh.status_code) == (401, 401)


def _write_routes() -> list[tuple[str, str]]:
    """Every write operation on /api/v1 resources, from the OpenAPI schema (path ids set to 1)."""
    schema = create_app(isolated_settings()).openapi()
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", "1", path))
        for path, operations in schema["paths"].items()
        if path.startswith("/api/v1/") and not path.startswith("/api/v1/auth/")
        for method in operations
        if method in {"post", "put", "patch", "delete"}
    ]


async def test_viewer_can_read_but_every_write_route_returns_403(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards the viewer role: rejects any POST/PATCH/DELETE route a viewer is allowed to call."""
    await make_user(db_session, email="viewer@fleet.test")
    headers = await bearer(anonymous_client, "viewer@fleet.test")
    write_routes = _write_routes()

    read = await anonymous_client.get("/api/v1/vehicles", headers=headers)
    responses = {
        (method, path): await anonymous_client.request(method, path, json={}, headers=headers)
        for method, path in write_routes
    }

    assert read.status_code == 200
    assert len(write_routes) == 12  # create, patch, delete for each of the 4 resources
    assert {key: r.status_code for key, r in responses.items()} == dict.fromkeys(responses, 403)
    assert all(r.json()["error"]["code"] == "forbidden" for r in responses.values())


async def test_admin_can_create_update_and_delete(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards the admin role: rejects an admin being blocked from writes."""
    await make_user(db_session, email="admin@fleet.test", role=UserRole.ADMIN)
    headers = await bearer(anonymous_client, "admin@fleet.test")

    created = await anonymous_client.post(
        "/api/v1/vehicles",
        headers=headers,
        json={"plate": "ZZ900AD", "brand": "Fiat", "model": "Cronos", "year": 2024,
              "vehicle_type": "car"},
    )  # fmt: skip
    vehicle_url = f"/api/v1/vehicles/{created.json()['id']}"
    updated = await anonymous_client.patch(vehicle_url, headers=headers, json={"odometer_km": 10})
    deleted = await anonymous_client.delete(vehicle_url, headers=headers)

    assert (created.status_code, updated.status_code, deleted.status_code) == (201, 200, 204)


async def test_login_is_rate_limited_per_ip(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards brute-force protection: rejects an 11th login attempt within a minute from one IP."""
    await make_user(db_session)

    attempts = [await login(anonymous_client, "viewer@fleet.test", "guess") for _ in range(10)]
    blocked = await login(anonymous_client, "viewer@fleet.test", PASSWORD)

    assert {r.status_code for r in attempts} == {401}
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60


def test_openapi_declares_the_password_flow_for_authorize_button() -> None:
    """Guards /docs Authorize: rejects a schema without the OAuth2 password flow on resources."""
    schema = create_app(isolated_settings()).openapi()

    flows = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]
    vehicles_get = schema["paths"]["/api/v1/vehicles"]["get"]
    assert flows["password"]["tokenUrl"] == LOGIN
    assert vehicles_get["security"] == [{"OAuth2PasswordBearer": []}]
    assert "security" not in schema["paths"][LOGIN]["post"]
