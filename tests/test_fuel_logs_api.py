from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_driver, make_fuel_log, make_vehicle

FUEL_LOGS = "/api/v1/fuel-logs"


def new_log(vehicle_id: int, **overrides: object) -> dict[str, object]:
    return {
        "vehicle_id": vehicle_id,
        "filled_at": "2026-11-20T09:30:00-03:00",
        "liters": "42.50",
        "total_cost": "66300.00",
        "odometer_km": 48_650,
    } | overrides


async def test_create_fuel_log_returns_201(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards POST /fuel-logs: rejects a lost driver link or float-rounded liters."""
    vehicle = make_vehicle()
    driver = make_driver()
    db_session.add_all([vehicle, driver])
    await db_session.flush()

    response = await api_client.post(FUEL_LOGS, json=new_log(vehicle.id, driver_id=driver.id))

    assert response.status_code == 201
    body = response.json()
    assert (body["driver_id"], body["liters"]) == (driver.id, "42.50")
    assert datetime.fromisoformat(body["filled_at"]) == datetime(2026, 11, 20, 12, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    "overrides",
    [{"liters": "0"}, {"filled_at": "2026-11-20T09:30:00"}, {"total_cost": "-1"}],
    ids=["zero-liters", "naive-datetime", "negative-cost"],
)
async def test_create_invalid_fuel_log_returns_422(
    api_client: AsyncClient, db_session: AsyncSession, overrides: dict[str, object]
) -> None:
    """Guards fuel log validation: rejects zero liters, offset-less timestamps or negative cost."""
    vehicle = make_vehicle()
    db_session.add(vehicle)
    await db_session.flush()

    response = await api_client.post(FUEL_LOGS, json=new_log(vehicle.id, **overrides))

    assert response.status_code == 422


async def test_create_fuel_log_with_unknown_driver_returns_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards driver references: rejects a fuel log pointing at a nonexistent driver."""
    vehicle = make_vehicle()
    db_session.add(vehicle)
    await db_session.flush()

    response = await api_client.post(FUEL_LOGS, json=new_log(vehicle.id, driver_id=999_999))

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Driver 999999 not found"


async def test_list_fuel_logs_date_range_uses_argentina_days(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards date filters: rejects UTC-day bucketing (01:30 UTC is the previous day in UTC-3)."""
    vehicle = make_vehicle()
    late_evening = make_fuel_log(vehicle, filled_at=datetime(2026, 3, 10, 1, 30, tzinfo=UTC))
    db_session.add(late_evening)
    await db_session.flush()

    on_ninth = await api_client.get(
        FUEL_LOGS, params={"filled_from": "2026-03-09", "filled_to": "2026-03-09"}
    )
    on_tenth = await api_client.get(
        FUEL_LOGS, params={"filled_from": "2026-03-10", "filled_to": "2026-03-10"}
    )

    assert [f["id"] for f in on_ninth.json()["items"]] == [late_evening.id]
    assert on_tenth.json()["total"] == 0


async def test_list_fuel_logs_filters_by_vehicle_and_driver(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards fuel log filters: rejects ignoring vehicle_id or driver_id."""
    first, second = make_vehicle(plate="ZZ001AA"), make_vehicle(plate="ZZ002AA")
    driver = make_driver()
    db_session.add_all(
        [
            make_fuel_log(first, driver=driver),
            make_fuel_log(first),
            make_fuel_log(second, driver=driver),
        ]
    )
    await db_session.flush()

    response = await api_client.get(
        FUEL_LOGS, params={"vehicle_id": first.id, "driver_id": driver.id}
    )

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["vehicle_id"] == first.id


async def test_patch_fuel_log_can_clear_driver(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards nullable fields in PATCH: rejects refusing driver_id null or changing other fields."""
    log = make_fuel_log(make_vehicle(), driver=make_driver())
    db_session.add(log)
    await db_session.flush()

    response = await api_client.patch(f"{FUEL_LOGS}/{log.id}", json={"driver_id": None})

    assert response.status_code == 200
    assert response.json()["driver_id"] is None
    assert response.json()["liters"] == "40.00"


async def test_get_then_delete_fuel_log(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """Guards fuel log GET/DELETE: rejects a wrong record, non-204 delete or a log left behind."""
    log = make_fuel_log(make_vehicle())
    db_session.add(log)
    await db_session.flush()

    fetched = await api_client.get(f"{FUEL_LOGS}/{log.id}")
    deleted = await api_client.delete(f"{FUEL_LOGS}/{log.id}")
    after = await api_client.get(f"{FUEL_LOGS}/{log.id}")

    assert (fetched.status_code, fetched.json()["id"]) == (200, log.id)
    assert deleted.status_code == 204
    assert after.status_code == 404
    assert after.json()["error"]["message"] == f"Fuel log {log.id} not found"


async def test_create_fuel_log_for_missing_vehicle_returns_404(api_client: AsyncClient) -> None:
    """Guards vehicle references: rejects a fuel log for a nonexistent vehicle."""
    response = await api_client.post(FUEL_LOGS, json=new_log(999_999))

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Vehicle 999999 not found"


async def test_inverted_fuel_log_date_range_returns_422(api_client: AsyncClient) -> None:
    """Guards range validation: rejects silently returning nothing when from > to."""
    response = await api_client.get(
        FUEL_LOGS, params={"filled_from": "2026-05-01", "filled_to": "2026-04-01"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_data"
