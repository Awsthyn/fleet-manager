"""Metrics endpoints, checked against small hand-built datasets with exactly known answers."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.security import hash_password
from app.models import MaintenanceType, User, UserRole, VehicleStatus
from app.repositories.metrics_repository import add_months, month_start
from tests.factories import make_driver, make_fuel_log, make_maintenance, make_vehicle

METRICS = "/api/v1/metrics"


def local_noon(day: date) -> datetime:
    return datetime.combine(day, time(12, 0), tzinfo=clock.BUSINESS_TZ)


async def test_summary_counts_statuses_drivers_licenses_and_overdue(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards /summary: rejects wrong counts, missing zero statuses or off-by-one license edges."""
    today = clock.today()
    km_overdue = make_vehicle(plate="ZZ001AA", odometer_km=20_000)
    two_overdue = make_vehicle(plate="ZZ002AA", odometer_km=5_000)
    fine = make_vehicle(plate="ZZ003AA", status=VehicleStatus.IN_MAINTENANCE, odometer_km=5_000)
    db_session.add_all(
        [
            make_maintenance(km_overdue, odometer_km=9_000, next_due_km=19_999, next_due_date=None),
            make_maintenance(
                two_overdue,
                performed_at=today - timedelta(days=200),
                odometer_km=1_000,
                next_due_km=50_000,
                next_due_date=today - timedelta(days=1),
            ),
            make_maintenance(
                two_overdue,
                maintenance_type=MaintenanceType.BRAKES,
                odometer_km=1_000,
                next_due_km=4_999,
                next_due_date=None,
            ),
            make_maintenance(
                fine,
                odometer_km=1_000,
                next_due_km=5_001,
                performed_at=today - timedelta(days=10),
                next_due_date=today,  # due today is not overdue yet
            ),
            # An older, overdue oil change superseded by the one above: must not count.
            make_maintenance(
                fine,
                odometer_km=100,
                next_due_km=900,
                performed_at=today - timedelta(days=300),
                next_due_date=None,
            ),
            make_driver(license_number="L-1", license_expiry=today),
            make_driver(license_number="L-2", license_expiry=today + timedelta(days=30)),
            make_driver(license_number="L-3", license_expiry=today + timedelta(days=31)),
            make_driver(license_number="L-4", license_expiry=today - timedelta(days=1)),
            make_driver(
                license_number="L-5", license_expiry=today + timedelta(days=5), is_active=False
            ),
        ]
    )
    await db_session.flush()

    body = (await api_client.get(f"{METRICS}/summary")).json()

    assert body["as_of"] == today.isoformat()
    assert body["vehicles"] == {
        "total": 3,
        "by_status": {"active": 2, "in_maintenance": 1, "inactive": 0},
    }
    assert body["drivers"] == {"active": 4, "licenses_expiring_soon": 2, "licenses_expired": 1}
    assert body["maintenance"] == {"overdue": 3, "vehicles_with_overdue": 2}


async def test_upcoming_maintenance_orders_by_urgency_with_reason(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards /maintenance/upcoming: rejects wrong order, reason, km estimate or window edge."""
    today = clock.today()
    by_date_soon = make_vehicle(plate="ZZ100DT", odometer_km=1_000)
    by_date_late = make_vehicle(plate="ZZ200DT", odometer_km=1_000)
    by_km = make_vehicle(plate="ZZ300KM", odometer_km=20_000)
    overdue = make_vehicle(plate="ZZ400OD", odometer_km=20_000)
    km_no_usage = make_vehicle(plate="ZZ500NU", odometer_km=20_000)
    db_session.add_all(
        [
            make_maintenance(
                by_date_soon,
                performed_at=today - timedelta(days=100),
                odometer_km=500,
                next_due_km=None,
                next_due_date=today + timedelta(days=10),
            ),
            make_maintenance(
                by_date_late,
                performed_at=today - timedelta(days=100),
                odometer_km=500,
                next_due_km=None,
                next_due_date=today + timedelta(days=40),
            ),
            # 1,500 km left at 100 km/day of recent usage -> due in 15 days, by km.
            make_maintenance(by_km, odometer_km=11_500, next_due_km=21_500, next_due_date=None),
            make_fuel_log(
                by_km, filled_at=local_noon(today - timedelta(days=20)), odometer_km=18_000
            ),
            make_fuel_log(by_km, filled_at=local_noon(today), odometer_km=20_000),
            # 300 km past due at 100 km/day -> 3 days overdue.
            make_maintenance(overdue, odometer_km=9_700, next_due_km=19_700, next_due_date=None),
            make_fuel_log(
                overdue, filled_at=local_noon(today - timedelta(days=10)), odometer_km=19_000
            ),
            make_fuel_log(overdue, filled_at=local_noon(today), odometer_km=20_000),
            # Km left but no usage data: cannot estimate, so it is not listed yet.
            make_maintenance(
                km_no_usage, odometer_km=11_000, next_due_km=21_000, next_due_date=None
            ),
        ]
    )
    await db_session.flush()

    within_30 = (
        await api_client.get(f"{METRICS}/maintenance/upcoming", params={"days": 30})
    ).json()
    within_60 = (
        await api_client.get(f"{METRICS}/maintenance/upcoming", params={"days": 60})
    ).json()

    summary = [
        (
            i["plate"],
            i["state"],
            i["reason"],
            i["days_until_due"],
            i["km_remaining"],
            i["km_estimate_used"],
        )
        for i in within_30["items"]
    ]
    assert summary == [
        ("ZZ400OD", "overdue", "km", -3, -300, True),
        ("ZZ100DT", "upcoming", "date", 10, None, False),
        ("ZZ300KM", "upcoming", "km", 15, 1_500, True),
    ]
    assert [i["plate"] for i in within_60["items"]] == ["ZZ400OD", "ZZ100DT", "ZZ300KM", "ZZ200DT"]


async def test_monthly_costs_are_exact_per_month_with_totals_and_top_vehicles(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards /costs/monthly: rejects wrong sums, missing zero months, UTC bucketing or bad top."""
    this_month = month_start(clock.today())
    last_month = add_months(this_month, -1)
    first = make_vehicle(plate="ZZ001CC")
    second = make_vehicle(plate="ZZ002CC")
    db_session.add_all(
        [
            make_maintenance(
                first, performed_at=this_month, cost=Decimal("100.00"), next_due_date=None
            ),
            make_maintenance(
                second, performed_at=this_month, cost=Decimal("50.50"), next_due_date=None
            ),
            make_maintenance(
                second, performed_at=last_month, cost=Decimal("10.00"), next_due_date=None
            ),
            # Outside the 3-month window: must not count anywhere.
            make_maintenance(
                second,
                performed_at=add_months(this_month, -3),
                cost=Decimal("999.00"),
                next_due_date=None,
            ),
            make_fuel_log(first, filled_at=local_noon(this_month), total_cost=Decimal("20.25")),
            # 01:30 UTC on the 1st is still the previous month in Argentina (UTC-3).
            make_fuel_log(
                first,
                filled_at=datetime.combine(this_month, time(1, 30), tzinfo=UTC),
                total_cost=Decimal("5.00"),
            ),
        ]
    )
    await db_session.flush()

    body = (await api_client.get(f"{METRICS}/costs/monthly", params={"months": 3})).json()

    two_months_ago = add_months(this_month, -2)
    assert body["months"] == [
        {
            "month": f"{two_months_ago:%Y-%m}",
            "maintenance": "0.00",
            "fuel": "0.00",
            "total": "0.00",
        },
        {"month": f"{last_month:%Y-%m}", "maintenance": "10.00", "fuel": "5.00", "total": "15.00"},
        {
            "month": f"{this_month:%Y-%m}",
            "maintenance": "150.50",
            "fuel": "20.25",
            "total": "170.75",
        },
    ]
    assert body["totals"] == {"maintenance": "160.50", "fuel": "25.25", "total": "185.75"}
    assert [
        (v["plate"], v["maintenance"], v["fuel"], v["total"]) for v in body["top_vehicles"]
    ] == [
        ("ZZ001CC", "100.00", "25.25", "125.25"),
        ("ZZ002CC", "60.50", "0.00", "60.50"),
    ]


async def test_top_vehicles_is_limited_to_five_most_expensive(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards the top-5 list: rejects more than five vehicles or a wrong ordering."""
    this_month = month_start(clock.today())
    vehicles = [make_vehicle(plate=f"ZZ{n:03d}TP") for n in range(7)]
    db_session.add_all(
        [
            make_maintenance(
                v, performed_at=this_month, cost=Decimal(10 * (n + 1)), next_due_date=None
            )
            for n, v in enumerate(vehicles)
        ]
    )
    await db_session.flush()

    body = (await api_client.get(f"{METRICS}/costs/monthly", params={"months": 1})).json()

    assert [v["plate"] for v in body["top_vehicles"]] == [
        "ZZ006TP",
        "ZZ005TP",
        "ZZ004TP",
        "ZZ003TP",
        "ZZ002TP",
    ]


async def test_fuel_efficiency_uses_consecutive_fills(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards /fuel/efficiency: rejects counting first fills, stalled odometers or wrong km/l."""
    efficient = make_vehicle(plate="ZZ001FE")
    thirsty = make_vehicle(plate="ZZ002FE")
    single_fill = make_vehicle(plate="ZZ003FE")
    start = datetime(2026, 3, 1, 12, tzinfo=UTC)
    db_session.add_all(
        [
            # First fill only sets the baseline; then 500 km / 50 L and 600 km / 40 L.
            make_fuel_log(efficient, filled_at=start, odometer_km=1_000, liters=Decimal("40")),
            make_fuel_log(
                efficient,
                filled_at=start + timedelta(days=5),
                odometer_km=1_500,
                liters=Decimal("50"),
            ),
            make_fuel_log(
                efficient,
                filled_at=start + timedelta(days=9),
                odometer_km=2_100,
                liters=Decimal("40"),
            ),
            # A repeated odometer reading (distance 0) must be ignored, not divide the average.
            make_fuel_log(
                efficient,
                filled_at=start + timedelta(days=10),
                odometer_km=2_100,
                liters=Decimal("5"),
            ),
            # 300 km / 60 L = 5 km/l.
            make_fuel_log(thirsty, filled_at=start, odometer_km=10_000, liters=Decimal("60")),
            make_fuel_log(
                thirsty,
                filled_at=start + timedelta(days=3),
                odometer_km=10_300,
                liters=Decimal("60"),
            ),
            make_fuel_log(single_fill, filled_at=start, odometer_km=500),
        ]
    )
    await db_session.flush()

    body = (await api_client.get(f"{METRICS}/fuel/efficiency")).json()

    rows = [
        (v["plate"], v["fills_counted"], v["distance_km"], v["liters"], v["km_per_liter"])
        for v in body["vehicles"]
    ]
    # 1,100 km / 90 L = 12.22 (weighted by distance, not the mean of 10.00 and 15.00).
    assert rows == [("ZZ001FE", 2, 1_100, "90.00", "12.22"), ("ZZ002FE", 1, 300, "60.00", "5.00")]
    assert body["fleet_km_per_liter"] == "9.33"  # 1,400 km / 150 L


async def test_metrics_with_no_data_return_zeros_not_errors(api_client: AsyncClient) -> None:
    """Guards empty databases: rejects errors or nulls where zeros are expected."""
    summary = (await api_client.get(f"{METRICS}/summary")).json()
    costs = (await api_client.get(f"{METRICS}/costs/monthly", params={"months": 2})).json()
    efficiency = (await api_client.get(f"{METRICS}/fuel/efficiency")).json()
    upcoming = await api_client.get(f"{METRICS}/maintenance/upcoming")

    assert summary["vehicles"]["by_status"] == {"active": 0, "in_maintenance": 0, "inactive": 0}
    assert costs["totals"] == {"maintenance": "0.00", "fuel": "0.00", "total": "0.00"}
    assert len(costs["months"]) == 2
    assert efficiency == {"fleet_km_per_liter": None, "vehicles": []}
    assert (upcoming.status_code, upcoming.json()["items"]) == (200, [])


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/maintenance/upcoming", {"days": 0}),
        ("/maintenance/upcoming", {"days": 366}),
        ("/costs/monthly", {"months": 0}),
        ("/costs/monthly", {"months": 25}),
    ],
)
async def test_metrics_reject_out_of_range_windows(
    api_client: AsyncClient, path: str, params: dict[str, int]
) -> None:
    """Guards window bounds: rejects days outside 1-365 or months outside 1-24."""
    response = await api_client.get(f"{METRICS}{path}", params=params)

    assert response.status_code == 422


async def test_viewer_can_read_metrics_and_anonymous_cannot(
    anonymous_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards metrics access: rejects blocking viewers or serving metrics without a token."""
    db_session.add(
        User(
            email="viewer@fleet.test",
            hashed_password=hash_password("viewer-pass"),
            role=UserRole.VIEWER,
        )
    )
    await db_session.flush()
    token = (
        await anonymous_client.post(
            "/api/v1/auth/login", data={"username": "viewer@fleet.test", "password": "viewer-pass"}
        )
    ).json()["access_token"]

    paths = ["/summary", "/maintenance/upcoming", "/costs/monthly", "/fuel/efficiency"]
    as_viewer = [
        (
            await anonymous_client.get(
                f"{METRICS}{p}", headers={"Authorization": f"Bearer {token}"}
            )
        ).status_code
        for p in paths
    ]
    anonymous = [(await anonymous_client.get(f"{METRICS}{p}")).status_code for p in paths]

    assert as_viewer == [200, 200, 200, 200]
    assert anonymous == [401, 401, 401, 401]
