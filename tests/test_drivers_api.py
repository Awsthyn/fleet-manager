from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_driver, make_vehicle

DRIVERS = "/api/v1/drivers"
NEW_DRIVER = {
    "full_name": "  Lucía Benítez ",
    "license_number": "lic-30111222",
    "license_expiry": "2028-04-30",
    "phone": "+54 9 11 0000-1234",
}


async def test_create_and_get_driver_round_trip(api_client: AsyncClient) -> None:
    """Guards POST/GET /drivers: rejects unnormalized name/license or data lost on the way back."""
    created = await api_client.post(DRIVERS, json=NEW_DRIVER)
    fetched = await api_client.get(f"{DRIVERS}/{created.json()['id']}")

    assert created.status_code == 201
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["full_name"] == "Lucía Benítez"
    assert body["license_number"] == "LIC-30111222"
    assert body["is_active"] is True
    assert body == created.json()


async def test_create_driver_with_duplicate_license_returns_409(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards license uniqueness over HTTP: rejects a 500 or 201 for a registered license."""
    db_session.add(make_driver(license_number="LIC-30111222"))
    await db_session.flush()

    response = await api_client.post(DRIVERS, json=NEW_DRIVER)

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "conflict",
        "message": "A driver with license number LIC-30111222 already exists",
        "details": None,
    }


async def test_patch_driver_changes_only_sent_fields(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards driver partial updates: rejects touching unsent fields."""
    driver = make_driver(full_name="Tomás Díaz")
    db_session.add(driver)
    await db_session.flush()

    response = await api_client.patch(f"{DRIVERS}/{driver.id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["full_name"] == "Tomás Díaz"


async def test_delete_driver_unassigns_their_vehicle(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards driver deletion: rejects a 409/500 or a vehicle still pointing at the driver."""
    driver = make_driver()
    vehicle = make_vehicle(assigned_driver=driver)
    db_session.add(vehicle)
    await db_session.flush()

    deleted = await api_client.delete(f"{DRIVERS}/{driver.id}")
    vehicle_after = await api_client.get(f"/api/v1/vehicles/{vehicle.id}")

    assert deleted.status_code == 204
    assert vehicle_after.json()["assigned_driver"] is None


async def test_list_drivers_filters_by_active_flag_and_search(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards driver filters: rejects ignoring is_active or a case-sensitive name search."""
    db_session.add_all(
        [
            make_driver(full_name="Ana Gómez", license_number="LIC-1"),
            make_driver(full_name="Bruno Acosta", license_number="LIC-2", is_active=False),
            make_driver(full_name="Carla Gómez", license_number="LIC-3"),
        ]
    )
    await db_session.flush()

    active = await api_client.get(DRIVERS, params={"is_active": "true"})
    search = await api_client.get(DRIVERS, params={"q": "GÓMEZ"})

    assert [d["full_name"] for d in active.json()["items"]] == ["Ana Gómez", "Carla Gómez"]
    assert search.json()["total"] == 2


async def test_patch_driver_to_an_existing_license_returns_409(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards license uniqueness on update: rejects taking a license another driver holds."""
    db_session.add(make_driver(license_number="LIC-TAKEN"))
    other = make_driver(license_number="LIC-OTHER")
    db_session.add(other)
    await db_session.flush()

    response = await api_client.patch(f"{DRIVERS}/{other.id}", json={"license_number": "lic-taken"})

    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "A driver with license number LIC-TAKEN already exists"
    )


async def test_get_missing_driver_returns_404(api_client: AsyncClient) -> None:
    """Guards the driver 404: rejects a 200/500 for an unknown driver id."""
    response = await api_client.get(f"{DRIVERS}/999999")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Driver 999999 not found"
