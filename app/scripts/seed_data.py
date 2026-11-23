"""Deterministic generator of fictional fleet data.

Everything is derived from a fixed seed plus a reference date (``today``): the same pair always
produces exactly the same data. Dates are relative to ``today`` so that "license expiring within
30 days" and "overdue service" stay true whenever the seed is run.

All data is fictional:
- Plates use the Mercosur layout with the prefix ``ZZ``, a series that is not issued yet.
- Phone numbers use the ``0000`` exchange, which is not assigned to subscribers.
- Names are random combinations of common first names and surnames.
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import MaintenanceType, VehicleStatus, VehicleType

SEED = 20261123
HISTORY_DAYS = 182  # about six months
ARGENTINA_TZ = timezone(timedelta(hours=-3))

VEHICLE_COUNT = 25
DRIVER_COUNT = 12
ASSIGNED_DRIVER_COUNT = 10
EXPIRING_LICENSE_COUNT = 3  # expire within the next 30 days
EXPIRED_LICENSE_COUNT = 1  # already expired, driver inactive

# Indexes into the vehicle list.
IN_MAINTENANCE_VEHICLES = frozenset({5, 17})
INACTIVE_VEHICLES = frozenset({22})
SKIPPED_SERVICE_VEHICLES = frozenset({2, 9, 14, 20})  # oil change never done -> overdue

FIRST_NAMES = (
    "Lucía", "Martín", "Sofía", "Mateo", "Valentina", "Santiago", "Camila", "Joaquín",
    "Florencia", "Tomás", "Agustina", "Nicolás", "Julieta", "Facundo", "Micaela", "Ignacio",
)  # fmt: skip
LAST_NAMES = (
    "González", "Rodríguez", "Fernández", "López", "Martínez", "Pérez", "Gómez", "Sánchez",
    "Romero", "Díaz", "Álvarez", "Torres", "Ruiz", "Ramírez", "Acosta", "Benítez",
)  # fmt: skip


CAR, VAN, TRUCK, MOTORCYCLE = (
    VehicleType.CAR,
    VehicleType.VAN,
    VehicleType.TRUCK,
    VehicleType.MOTORCYCLE,
)
# Per type: (min, max) km driven on a working day, and the oil-change interval in km.
_USAGE: dict[VehicleType, tuple[tuple[int, int], int]] = {
    CAR: ((60, 120), 10_000),
    VAN: ((100, 180), 15_000),
    TRUCK: ((150, 300), 20_000),
    MOTORCYCLE: ((40, 80), 3_000),
}


@dataclass(frozen=True)
class _Profile:
    vehicle_type: VehicleType
    brand: str
    model: str
    km_per_liter: float
    tank_liters: int
    cost_factor: Decimal

    @property
    def daily_km(self) -> tuple[int, int]:
        return _USAGE[self.vehicle_type][0]

    @property
    def oil_interval_km(self) -> int:
        return _USAGE[self.vehicle_type][1]


_CATALOG: tuple[tuple[_Profile, int], ...] = (
    # (profile, how many vehicles of it)
    (_Profile(CAR, "Toyota", "Corolla", 13.0, 50, Decimal("1.0")), 2),
    (_Profile(CAR, "Toyota", "Etios", 14.5, 45, Decimal("0.9")), 1),
    (_Profile(CAR, "Volkswagen", "Gol Trend", 13.5, 55, Decimal("0.9")), 2),
    (_Profile(CAR, "Fiat", "Cronos", 13.5, 48, Decimal("0.9")), 2),
    (_Profile(CAR, "Chevrolet", "Onix", 14.0, 44, Decimal("0.9")), 2),
    (_Profile(CAR, "Renault", "Sandero", 13.0, 50, Decimal("0.9")), 1),
    (_Profile(CAR, "Peugeot", "208", 14.0, 47, Decimal("1.0")), 2),
    (_Profile(VAN, "Renault", "Kangoo", 11.0, 60, Decimal("1.2")), 2),
    (_Profile(VAN, "Fiat", "Fiorino", 12.0, 48, Decimal("1.1")), 2),
    (_Profile(VAN, "Peugeot", "Partner", 11.5, 60, Decimal("1.2")), 1),
    (_Profile(VAN, "Mercedes-Benz", "Sprinter", 8.5, 75, Decimal("1.6")), 1),
    (_Profile(TRUCK, "Iveco", "Tector", 4.0, 300, Decimal("2.5")), 1),
    (_Profile(TRUCK, "Mercedes-Benz", "Atego", 4.2, 300, Decimal("2.5")), 1),
    (_Profile(TRUCK, "Ford", "Cargo 1723", 3.8, 275, Decimal("2.4")), 1),
    (_Profile(TRUCK, "Volkswagen", "Delivery 11.180", 5.0, 150, Decimal("2.2")), 1),
    (_Profile(MOTORCYCLE, "Honda", "CG 150 Titan", 38.0, 16, Decimal("0.35")), 1),
    (_Profile(MOTORCYCLE, "Yamaha", "YBR 125", 40.0, 13, Decimal("0.35")), 1),
    (_Profile(MOTORCYCLE, "Motomel", "S2 150", 36.0, 14, Decimal("0.3")), 1),
)

# Base costs in ARS for a regular car; multiplied by the profile's cost_factor.
_BASE_COST = {
    MaintenanceType.OIL_CHANGE: (Decimal(85_000), Decimal(120_000)),
    MaintenanceType.TIRES: (Decimal(380_000), Decimal(560_000)),
    MaintenanceType.BRAKES: (Decimal(140_000), Decimal(230_000)),
    MaintenanceType.INSPECTION: (Decimal(45_000), Decimal(70_000)),
    MaintenanceType.REPAIR: (Decimal(90_000), Decimal(420_000)),
    MaintenanceType.OTHER: (Decimal(30_000), Decimal(90_000)),
}
_NOTES = {
    MaintenanceType.OIL_CHANGE: "Engine oil and filter replaced.",
    MaintenanceType.TIRES: "Tires replaced, alignment and balancing.",
    MaintenanceType.BRAKES: "Brake pads replaced, fluid checked.",
    MaintenanceType.INSPECTION: "Periodic technical inspection passed.",
    MaintenanceType.REPAIR: "Corrective repair after a reported fault.",
    MaintenanceType.OTHER: "Minor service: wipers, bulbs and fluids.",
}
_EXTRA_TYPES = (
    MaintenanceType.TIRES,
    MaintenanceType.BRAKES,
    MaintenanceType.INSPECTION,
    MaintenanceType.REPAIR,
    MaintenanceType.OTHER,
)
_FUEL_PRICE_PER_LITER = Decimal(1_450)  # ARS at the start of the history
_MONTHLY_PRICE_INCREASE = 0.02
_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class SeedDriver:
    full_name: str
    license_number: str
    license_expiry: date
    phone: str
    is_active: bool


@dataclass(frozen=True)
class SeedMaintenance:
    maintenance_type: MaintenanceType
    performed_at: date
    odometer_km: int
    cost: Decimal
    notes: str
    next_due_km: int | None
    next_due_date: date | None


@dataclass(frozen=True)
class SeedFuelLog:
    filled_at: datetime
    liters: Decimal
    total_cost: Decimal
    odometer_km: int
    driver_license: str | None


@dataclass(frozen=True)
class SeedVehicle:
    plate: str
    brand: str
    model: str
    year: int
    vehicle_type: VehicleType
    status: VehicleStatus
    odometer_km: int
    driver_license: str | None
    maintenance: tuple[SeedMaintenance, ...] = field(default=())
    fuel_logs: tuple[SeedFuelLog, ...] = field(default=())


@dataclass(frozen=True)
class SeedData:
    drivers: tuple[SeedDriver, ...]
    vehicles: tuple[SeedVehicle, ...]


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _random_cost(rng: random.Random, kind: MaintenanceType, factor: Decimal) -> Decimal:
    low, high = _BASE_COST[kind]
    return _money(Decimal(rng.uniform(float(low), float(high))) * factor)


def _generate_drivers(rng: random.Random, today: date) -> tuple[SeedDriver, ...]:
    names = rng.sample([(f, s) for f in FIRST_NAMES for s in LAST_NAMES], DRIVER_COUNT)
    license_numbers = rng.sample(range(20_000_000, 45_000_000), DRIVER_COUNT)
    drivers: list[SeedDriver] = []
    for i, ((first, last), number) in enumerate(zip(names, license_numbers, strict=True)):
        if i < EXPIRING_LICENSE_COUNT:
            expiry = today + timedelta(days=rng.randint(3, 28))
        elif i < EXPIRING_LICENSE_COUNT + EXPIRED_LICENSE_COUNT:
            expiry = today - timedelta(days=rng.randint(10, 40))
        else:
            expiry = today + timedelta(days=rng.randint(60, 1_500))
        drivers.append(
            SeedDriver(
                full_name=f"{first} {last}",
                license_number=f"LIC-{number}",
                license_expiry=expiry,
                phone=f"+54 9 11 0000-{1001 + i:04d}",
                is_active=expiry >= today,
            )
        )
    return tuple(drivers)


def _plates(rng: random.Random) -> list[str]:
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    plates: set[str] = set()
    while len(plates) < VEHICLE_COUNT:
        plates.add(f"ZZ{rng.randint(100, 999)}{rng.choice(letters)}{rng.choice(letters)}")
    return sorted(plates)


def _fill_time(rng: random.Random, day: date) -> datetime:
    local = datetime.combine(day, time(rng.randint(7, 20), rng.choice((0, 15, 30, 45))))
    return local.replace(tzinfo=ARGENTINA_TZ).astimezone(UTC)


def _simulate_history(
    rng: random.Random,
    profile: _Profile,
    start_odometer: int,
    start: date,
    end: date,
    skip_service: bool,
    driver_license: str | None,
) -> tuple[int, tuple[SeedMaintenance, ...], tuple[SeedFuelLog, ...]]:
    maintenance: list[SeedMaintenance] = []
    fuel_logs: list[SeedFuelLog] = []

    def oil_change(day: date, odometer: int) -> SeedMaintenance:
        return SeedMaintenance(
            maintenance_type=MaintenanceType.OIL_CHANGE,
            performed_at=day,
            odometer_km=odometer,
            cost=_random_cost(rng, MaintenanceType.OIL_CHANGE, profile.cost_factor),
            notes=_NOTES[MaintenanceType.OIL_CHANGE],
            next_due_km=odometer + profile.oil_interval_km,
            next_due_date=day + timedelta(days=180),
        )

    odometer = start_odometer
    first_service = oil_change(start, odometer)
    maintenance.append(first_service)
    next_due_km = first_service.next_due_km or 0
    next_due_date = first_service.next_due_date or end

    total_days = (end - start).days
    extra_days = {
        rng.randint(10, total_days - 1): rng.choice(_EXTRA_TYPES) for _ in range(rng.randint(1, 3))
    }
    km_since_fill = 0
    fill_after_km = int(profile.tank_liters * profile.km_per_liter * rng.uniform(0.55, 0.8))

    for offset in range(1, total_days + 1):
        day = start + timedelta(days=offset)
        if day.weekday() < 6:  # no trips on Sundays
            driven = rng.randint(*profile.daily_km)
            odometer += driven
            km_since_fill += driven

        if km_since_fill >= fill_after_km:
            liters = _money(Decimal(km_since_fill / profile.km_per_liter * rng.uniform(0.93, 1.07)))
            price = _FUEL_PRICE_PER_LITER * Decimal((1 + _MONTHLY_PRICE_INCREASE) ** (offset / 30))
            fuel_logs.append(
                SeedFuelLog(
                    filled_at=_fill_time(rng, day),
                    liters=liters,
                    total_cost=_money(liters * price),
                    odometer_km=odometer,
                    driver_license=driver_license,
                )
            )
            km_since_fill = 0
            fill_after_km = int(profile.tank_liters * profile.km_per_liter * rng.uniform(0.55, 0.8))

        if not skip_service and (odometer >= next_due_km or day >= next_due_date):
            service = oil_change(day, odometer)
            maintenance.append(service)
            next_due_km = service.next_due_km or 0
            next_due_date = service.next_due_date or end

        if offset in extra_days:
            kind = extra_days[offset]
            next_km = {MaintenanceType.TIRES: 40_000, MaintenanceType.BRAKES: 30_000}.get(kind)
            maintenance.append(
                SeedMaintenance(
                    maintenance_type=kind,
                    performed_at=day,
                    odometer_km=odometer,
                    cost=_random_cost(rng, kind, profile.cost_factor),
                    notes=_NOTES[kind],
                    next_due_km=odometer + next_km if next_km else None,
                    next_due_date=(
                        day + timedelta(days=365) if kind is MaintenanceType.INSPECTION else None
                    ),
                )
            )

    return odometer, tuple(maintenance), tuple(fuel_logs)


def generate(today: date, seed: int = SEED) -> SeedData:
    """Generate the full fictional dataset for the given reference date."""
    rng = random.Random(seed)  # noqa: S311 - reproducible fake data, not security
    drivers = _generate_drivers(rng, today)
    profiles = [profile for profile, count in _CATALOG for _ in range(count)]
    rng.shuffle(profiles)
    plates = _plates(rng)

    # Assign active drivers, expiring licenses first, to the first active vehicles.
    assignable = [d.license_number for d in drivers if d.is_active][:ASSIGNED_DRIVER_COUNT]
    start = today - timedelta(days=HISTORY_DAYS)

    vehicles: list[SeedVehicle] = []
    for i, (profile, plate) in enumerate(zip(profiles, plates, strict=True)):
        if i in INACTIVE_VEHICLES:
            status = VehicleStatus.INACTIVE
        elif i in IN_MAINTENANCE_VEHICLES:
            status = VehicleStatus.IN_MAINTENANCE
        else:
            status = VehicleStatus.ACTIVE
        driver_license = (
            assignable.pop(0) if status is VehicleStatus.ACTIVE and assignable else None
        )

        year = rng.randint(today.year - 9, today.year)
        age = max(today.year - year, 0)
        yearly_km = sum(profile.daily_km) // 2 * 300
        start_odometer = int(age * yearly_km * rng.uniform(0.7, 1.1)) + rng.randint(500, 3_000)
        # Inactive vehicles stopped being used two months ago.
        end = today - timedelta(days=60) if status is VehicleStatus.INACTIVE else today

        odometer, maintenance, fuel_logs = _simulate_history(
            random.Random(f"{seed}-{plate}"),  # noqa: S311 - reproducible fake data
            profile,
            start_odometer,
            start,
            end,
            skip_service=i in SKIPPED_SERVICE_VEHICLES,
            driver_license=driver_license,
        )
        vehicles.append(
            SeedVehicle(
                plate=plate,
                brand=profile.brand,
                model=profile.model,
                year=year,
                vehicle_type=profile.vehicle_type,
                status=status,
                odometer_km=odometer,
                driver_license=driver_license,
                maintenance=maintenance,
                fuel_logs=fuel_logs,
            )
        )

    return SeedData(drivers=drivers, vehicles=tuple(vehicles))
