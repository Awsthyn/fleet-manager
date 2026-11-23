from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.models import MaintenanceType, VehicleStatus, VehicleType
from tests.factories import make_driver, make_maintenance, make_vehicle

VEHICLES = "/api/v1/vehicles"
VEHICLE_KEYS = {
    "id",
    "plate",
    "brand",
    "model",
    "year",
    "vehicle_type",
    "status",
    "odometer_km",
    "assigned_driver",
    "created_at",
    "updated_at",
}
NEW_VEHICLE = {
    "plate": "ab 123 cd",
    "brand": "Toyota",
    "model": "Corolla",
    "year": 2023,
    "vehicle_type": "car",
    "odometer_km": 1_000,
}


async def test_create_vehicle_returns_201_with_normalized_plate_and_driver(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards POST /vehicles: rejects an unnormalized plate, a missing driver or extra fields."""
    driver = make_driver()
    db_session.add(driver)
    await db_session.flush()

    response = await api_client.post(VEHICLES, json=NEW_VEHICLE | {"assigned_driver_id": driver.id})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == VEHICLE_KEYS
    assert body["plate"] == "AB123CD"
    assert body["status"] == "active"
    assert body["assigned_driver"]["id"] == driver.id


async def test_create_vehicle_with_duplicate_plate_returns_409(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards plate uniqueness over HTTP: rejects a 500 or 201 for an already registered plate."""
    db_session.add(make_vehicle(plate="AB123CD"))
    await db_session.flush()

    response = await api_client.post(VEHICLES, json=NEW_VEHICLE)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "message": "A vehicle with plate AB123CD already exists",
            "details": None,
        }
    }


async def test_create_vehicle_with_unknown_driver_returns_404(api_client: AsyncClient) -> None:
    """Guards driver references: rejects creating a vehicle assigned to a nonexistent driver."""
    response = await api_client.post(VEHICLES, json=NEW_VEHICLE | {"assigned_driver_id": 999_999})

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Driver 999999 not found"


async def test_get_missing_vehicle_returns_404_error_body(api_client: AsyncClient) -> None:
    """Guards the 404 contract: rejects a different status or a non-uniform error body."""
    response = await api_client.get(f"{VEHICLES}/999999")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Vehicle 999999 not found",
        "details": None,
    }


async def test_patch_vehicle_changes_only_sent_fields(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards partial updates: rejects overwriting unsent fields or ignoring an unassign."""
    vehicle = make_vehicle(plate="ZZ111AA", brand="Fiat", assigned_driver=make_driver())
    db_session.add(vehicle)
    await db_session.flush()

    response = await api_client.patch(
        f"{VEHICLES}/{vehicle.id}",
        json={"status": "in_maintenance", "assigned_driver_id": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_maintenance"
    assert body["assigned_driver"] is None
    assert (body["plate"], body["brand"], body["odometer_km"]) == ("ZZ111AA", "Fiat", 10_000)


async def test_patch_vehicle_rejects_null_for_required_field(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards PATCH validation: rejects null on a non-nullable field instead of a 422."""
    vehicle = make_vehicle()
    db_session.add(vehicle)
    await db_session.flush()

    response = await api_client.patch(f"{VEHICLES}/{vehicle.id}", json={"brand": None})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "'brand' cannot be null" in error["details"][0]["msg"]


async def test_patch_vehicle_to_an_existing_plate_returns_409(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards uniqueness on update: rejects renaming a plate to one another vehicle uses."""
    db_session.add(make_vehicle(plate="ZZ111AA"))
    other = make_vehicle(plate="ZZ222BB")
    db_session.add(other)
    await db_session.flush()

    response = await api_client.patch(f"{VEHICLES}/{other.id}", json={"plate": "zz111aa"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_delete_vehicle_returns_204_and_then_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards DELETE: rejects a non-204 response or a vehicle that is still retrievable."""
    vehicle = make_vehicle()
    db_session.add_all([vehicle, make_maintenance(vehicle)])
    await db_session.flush()

    deleted = await api_client.delete(f"{VEHICLES}/{vehicle.id}")
    after = await api_client.get(f"{VEHICLES}/{vehicle.id}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert after.status_code == 404


async def test_list_vehicles_paginates_and_reports_total(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards pagination: rejects a wrong page slice, wrong order or a total limited to the page."""
    db_session.add_all([make_vehicle(plate=f"ZZ{n:03d}AA") for n in range(7)])
    await db_session.flush()

    response = await api_client.get(VEHICLES, params={"limit": 3, "offset": 3})

    body = response.json()
    assert response.status_code == 200
    assert (body["total"], body["limit"], body["offset"]) == (7, 3, 3)
    assert [v["plate"] for v in body["items"]] == ["ZZ003AA", "ZZ004AA", "ZZ005AA"]


@pytest.mark.parametrize("params", [{"limit": 101}, {"limit": 0}, {"offset": -1}])
async def test_list_vehicles_rejects_out_of_range_pagination(
    api_client: AsyncClient, params: dict[str, int]
) -> None:
    """Guards the page-size cap: rejects limit above 100, limit 0 or a negative offset."""
    response = await api_client.get(VEHICLES, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    ("params", "expected_plates"),
    [
        ({"status": "inactive"}, ["ZZ300CC"]),
        ({"vehicle_type": "truck"}, ["ZZ200BB"]),
        ({"q": "iveco"}, ["ZZ200BB"]),
        ({"q": "zz1"}, ["ZZ100AA"]),
        ({"q": "orolla"}, ["ZZ100AA"]),
    ],
)
async def test_list_vehicles_filters_by_status_type_and_search(
    api_client: AsyncClient,
    db_session: AsyncSession,
    params: dict[str, str],
    expected_plates: list[str],
) -> None:
    """Guards list filters: rejects ignoring status/type or a case-sensitive or partial search."""
    db_session.add_all(
        [
            make_vehicle(plate="ZZ100AA", brand="Toyota", model="Corolla"),
            make_vehicle(
                plate="ZZ200BB", brand="Iveco", model="Tector", vehicle_type=VehicleType.TRUCK
            ),
            make_vehicle(plate="ZZ300CC", brand="Fiat", status=VehicleStatus.INACTIVE),
        ]
    )
    await db_session.flush()

    response = await api_client.get(VEHICLES, params=params)

    assert [v["plate"] for v in response.json()["items"]] == expected_plates


async def test_list_vehicles_filters_by_overdue_maintenance(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards has_overdue_maintenance: rejects superseded services or missed km/date cases."""
    today = clock.today()
    by_km = make_vehicle(plate="ZZ100KM", odometer_km=20_000)
    by_date = make_vehicle(plate="ZZ200DT", odometer_km=5_000)
    superseded = make_vehicle(plate="ZZ300OK", odometer_km=20_000)
    no_history = make_vehicle(plate="ZZ400NO")
    db_session.add_all(
        [
            make_maintenance(
                by_km,
                odometer_km=5_000,
                next_due_km=15_000,
                performed_at=today - timedelta(30),
                next_due_date=None,
            ),
            make_maintenance(
                by_date,
                odometer_km=1_000,
                next_due_km=50_000,
                performed_at=today - timedelta(200),
                next_due_date=today - timedelta(1),
            ),
            # An old, overdue oil change replaced by a newer one that is not due yet.
            make_maintenance(
                superseded,
                odometer_km=5_000,
                next_due_km=15_000,
                performed_at=today - timedelta(90),
                next_due_date=None,
            ),
            make_maintenance(
                superseded,
                odometer_km=19_000,
                next_due_km=29_000,
                performed_at=today - timedelta(5),
                next_due_date=today + timedelta(180),
            ),
            # A different type with no due values never makes a vehicle overdue.
            make_maintenance(
                no_history,
                maintenance_type=MaintenanceType.REPAIR,
                cost=Decimal("1.00"),
                next_due_km=None,
                next_due_date=None,
            ),
        ]
    )
    await db_session.flush()

    overdue = await api_client.get(VEHICLES, params={"has_overdue_maintenance": "true"})
    not_overdue = await api_client.get(VEHICLES, params={"has_overdue_maintenance": "false"})

    assert [v["plate"] for v in overdue.json()["items"]] == ["ZZ100KM", "ZZ200DT"]
    assert [v["plate"] for v in not_overdue.json()["items"]] == ["ZZ300OK", "ZZ400NO"]


async def test_get_vehicle_includes_driver_and_five_latest_maintenance(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards the detail view: rejects a missing driver, over 5 records or wrong ordering."""
    today = clock.today()
    vehicle = make_vehicle(assigned_driver=make_driver(full_name="Camila Ruiz"))
    db_session.add_all(
        [
            make_maintenance(
                vehicle,
                performed_at=today - timedelta(days=10 * n),
                next_due_date=today + timedelta(days=1),
            )
            for n in range(7)
        ]
    )
    await db_session.flush()

    response = await api_client.get(f"{VEHICLES}/{vehicle.id}")

    body = response.json()
    dates = [m["performed_at"] for m in body["recent_maintenance"]]
    assert response.status_code == 200
    assert body["assigned_driver"]["full_name"] == "Camila Ruiz"
    assert len(dates) == 5
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == today.isoformat()


async def test_offset_past_the_end_returns_an_empty_page_with_the_total(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards the pagination edge: rejects an error or a zero total when offset exceeds the rows."""
    db_session.add_all([make_vehicle(plate=f"ZZ{n:03d}EN") for n in range(3)])
    await db_session.flush()

    response = await api_client.get(VEHICLES, params={"limit": 10, "offset": 50})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 3, "limit": 10, "offset": 50}
