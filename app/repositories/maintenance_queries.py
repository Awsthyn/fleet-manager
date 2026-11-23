"""Shared SQL building blocks for "which maintenance is due". One definition for every consumer.

Rule: for each (vehicle, maintenance type) only the most recent record counts, because a later
service of the same type supersedes an older due date or due km. That record is **overdue**
when its ``next_due_km`` is below the vehicle's current odometer or its ``next_due_date`` is
before today. Used by the vehicle list filter (A3) and the metrics endpoints (A5).
"""

from datetime import date

from sqlalchemy import ColumnElement, Subquery, func, or_, select

from app.models import MaintenanceRecord, Vehicle


def latest_records() -> Subquery:
    """Every maintenance record with ``rank`` = 1 for the latest one per (vehicle, type)."""
    return select(
        MaintenanceRecord.id,
        MaintenanceRecord.vehicle_id,
        MaintenanceRecord.maintenance_type,
        MaintenanceRecord.performed_at,
        MaintenanceRecord.next_due_km,
        MaintenanceRecord.next_due_date,
        func.row_number()
        .over(
            partition_by=(MaintenanceRecord.vehicle_id, MaintenanceRecord.maintenance_type),
            order_by=(MaintenanceRecord.performed_at.desc(), MaintenanceRecord.id.desc()),
        )
        .label("rank"),
    ).subquery("latest_records")


def is_overdue(latest: Subquery, today: date) -> ColumnElement[bool]:
    """Overdue condition for a ``latest_records()`` row joined to its Vehicle."""
    return or_(latest.c.next_due_km < Vehicle.odometer_km, latest.c.next_due_date < today)
