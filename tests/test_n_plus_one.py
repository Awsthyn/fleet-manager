"""N+1 guard for the vehicle list.

What N+1 is: listing N vehicles with one query, then loading each vehicle's driver with its own
query, for 1 + N queries in total. It looks fine with 3 rows in development and degrades
linearly in production (25 vehicles: 26 round trips; on Neon each round trip costs latency).

How this test detects it: a SQLAlchemy ``before_cursor_execute`` listener on the test connection
records every statement sent to PostgreSQL while ``GET /api/v1/vehicles`` runs. The list must
cost the same small, fixed number of SELECTs whether it returns 5 or 25 vehicles (each with its
own driver): one COUNT for the total, one for the page, one ``drivers.id IN (...)`` from
``selectinload``. A per-vehicle lazy load would make the count grow with the number of rows.
Note that with async SQLAlchemy and ``lazy="raise_on_sql"`` an accidental lazy load fails loudly
instead of querying; the count still catches N+1 written explicitly (e.g. awaiting one query per
row in a loop).
"""

from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import Connection, event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from tests.factories import make_driver, make_vehicle

MAX_SELECTS_FOR_VEHICLE_LIST = 3


@pytest.fixture
def executed_selects(db_session: AsyncSession) -> Iterator[list[str]]:
    """SELECT statements executed on the test connection (savepoint bookkeeping excluded)."""
    bind = db_session.bind
    assert isinstance(bind, AsyncConnection)
    statements: list[str] = []

    def record(
        _conn: Connection,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(bind.sync_connection, "before_cursor_execute", record)
    yield statements
    event.remove(bind.sync_connection, "before_cursor_execute", record)


async def _selects_to_list_vehicles(
    count: int, api_client: AsyncClient, db_session: AsyncSession, executed: list[str]
) -> int:
    db_session.add_all(
        [
            make_vehicle(
                plate=f"ZZ{count:02d}{n:03d}",
                assigned_driver=make_driver(license_number=f"LIC-{count}-{n}"),
            )
            for n in range(count)
        ]
    )
    await db_session.flush()
    # Forget the instances created above: otherwise the request would find vehicles and drivers
    # already in the session's identity map and never need to load drivers, hiding an N+1.
    db_session.expunge_all()
    executed.clear()

    response = await api_client.get("/api/v1/vehicles", params={"limit": 100})

    assert response.status_code == 200
    assert len(response.json()["items"]) == response.json()["total"]
    assert all(v["assigned_driver"] is not None for v in response.json()["items"])
    return len(executed)


async def test_vehicle_list_query_count_does_not_grow_with_rows(
    api_client: AsyncClient, db_session: AsyncSession, executed_selects: list[str]
) -> None:
    """Guards against N+1: rejects a vehicle list whose SELECT count grows with the row count."""
    with_5 = await _selects_to_list_vehicles(5, api_client, db_session, executed_selects)
    with_25 = await _selects_to_list_vehicles(20, api_client, db_session, executed_selects)

    assert with_5 == with_25
    assert with_25 <= MAX_SELECTS_FOR_VEHICLE_LIST, executed_selects
