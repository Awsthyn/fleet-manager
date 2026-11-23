"""Business time. The fleet operates in Argentina, so "today" and date filters use UTC-3."""

from datetime import date, datetime, time, timedelta, timezone

BUSINESS_TZ = timezone(timedelta(hours=-3))


def today() -> date:
    return datetime.now(BUSINESS_TZ).date()


def start_of_day(day: date) -> datetime:
    """Timezone-aware instant at which ``day`` begins in business time."""
    return datetime.combine(day, time.min, tzinfo=BUSINESS_TZ)
