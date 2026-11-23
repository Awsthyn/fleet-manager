from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MaintenanceType
from tests.factories import make_maintenance, make_vehicle

RECORDS = "/api/v1/maintenance-records"


def new_record(vehicle_id: int, **overrides: object) -> dict[str, object]:
    return {
        "vehicle_id": vehicle_id,
        "maintenance_type": "oil_change",
        "performed_at": "2026-11-02",
        "odometer_km": 48_200,
        "cost": "98500.00",
        "next_due_km": 58_200,
        "next_due_date": "2027-05-02",
    } | overrides


async def test_create_record_returns_201_with_decimal_cost(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards POST /maintenance-records: rejects a lost record or a float-rounded cost."""
    vehicle = make_vehicle()
    db_session.add(vehicle)
    await db_session.flush()

    response = await api_client.post(RECORDS, json=new_record(vehicle.id, cost="98500.10"))

    assert response.status_code == 201
    assert response.json()["cost"] == "98500.10"
    assert response.json()["vehicle_id"] == vehicle.id


async def test_create_record_for_missing_vehicle_returns_404(api_client: AsyncClient) -> None:
    """Guards vehicle references: rejects recording maintenance for a nonexistent vehicle."""
    response = await api_client.post(RECORDS, json=new_record(999_999))

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Vehicle 999999 not found"


@pytest.mark.parametrize(
    "overrides",
    [
        {"cost": "-1"},
        {"next_due_km": 48_200},
        {"next_due_date": "2026-11-02"},
        {"maintenance_type": "car_wash"},
    ],
    ids=["negative-cost", "due-km-not-ahead", "due-date-not-ahead", "unknown-type"],
)
async def test_create_invalid_record_returns_422(
    api_client: AsyncClient, db_session: AsyncSession, overrides: dict[str, object]
) -> None:
    """Guards input validation: rejects negative costs, stale due values or unknown types."""
    vehicle = make_vehicle()
    db_session.add(vehicle)
    await db_session.flush()

    response = await api_client.post(RECORDS, json=new_record(vehicle.id, **overrides))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_patch_conflicting_with_stored_values_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards partial updates against stored data: rejects an odometer past the stored next due."""
    record = make_maintenance(make_vehicle(), odometer_km=9_000, next_due_km=19_000)
    db_session.add(record)
    await db_session.flush()

    response = await api_client.patch(f"{RECORDS}/{record.id}", json={"odometer_km": 25_000})
    unchanged = await api_client.get(f"{RECORDS}/{record.id}")

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_data",
        "message": "next_due_km must be greater than odometer_km",
        "details": None,
    }
    assert unchanged.json()["odometer_km"] == 9_000


async def test_list_records_filters_by_type_and_inclusive_date_range(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards record filters: rejects exclusive date bounds or ignoring the type filter."""
    vehicle = make_vehicle()
    db_session.add_all(
        [
            make_maintenance(vehicle, performed_at=date(2026, 1, 1), next_due_date=None),
            make_maintenance(vehicle, performed_at=date(2026, 1, 31), next_due_date=None),
            make_maintenance(vehicle, performed_at=date(2026, 2, 1), next_due_date=None),
            make_maintenance(
                vehicle,
                performed_at=date(2026, 1, 15),
                maintenance_type=MaintenanceType.TIRES,
                next_due_date=None,
            ),
        ]
    )
    await db_session.flush()

    response = await api_client.get(
        RECORDS,
        params={
            "vehicle_id": vehicle.id,
            "maintenance_type": "oil_change",
            "performed_from": "2026-01-01",
            "performed_to": "2026-01-31",
        },
    )

    assert [r["performed_at"] for r in response.json()["items"]] == ["2026-01-31", "2026-01-01"]


async def test_list_records_with_inverted_date_range_returns_422(api_client: AsyncClient) -> None:
    """Guards range validation: rejects silently returning nothing for from > to."""
    response = await api_client.get(
        RECORDS, params={"performed_from": "2026-02-01", "performed_to": "2026-01-01"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_data"


async def test_delete_record_returns_204_and_then_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards record deletion: rejects a non-204 response or a record still retrievable."""
    record = make_maintenance(make_vehicle())
    db_session.add(record)
    await db_session.flush()

    deleted = await api_client.delete(f"{RECORDS}/{record.id}")
    after = await api_client.get(f"{RECORDS}/{record.id}")

    assert deleted.status_code == 204
    assert after.status_code == 404


async def test_patch_record_changes_only_sent_fields(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards a valid PATCH: rejects failing, rounding the cost or clearing unsent fields."""
    record = make_maintenance(make_vehicle(), notes="Original note")
    db_session.add(record)
    await db_session.flush()

    response = await api_client.patch(
        f"{RECORDS}/{record.id}", json={"cost": "123456.78", "next_due_date": None}
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["cost"], body["next_due_date"]) == ("123456.78", None)
    assert (body["notes"], body["odometer_km"], body["next_due_km"]) == (
        "Original note",
        9_000,
        19_000,
    )
