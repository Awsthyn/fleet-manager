import type { MaintenanceType, VehicleStatus, VehicleType } from "@/lib/types";

const ars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 0,
});
const integer = new Intl.NumberFormat("en-US");

/** Amounts come from the API as decimal strings (exact); display without cents. */
export function formatMoney(amount: string | number): string {
  return ars.format(Number(amount));
}

export function formatKm(km: number): string {
  return `${integer.format(km)} km`;
}

/** API dates are calendar days (YYYY-MM-DD); format them without a timezone shift. */
export function formatDate(day: string): string {
  const [year, month, date] = day.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date)).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "2026-11" -> "Nov 26" */
export function formatMonth(month: string): string {
  const [year, m] = month.split("-").map(Number);
  return new Date(Date.UTC(year, m - 1, 1)).toLocaleDateString("en-US", {
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  });
}

/** Whole days from `fromDay` to `toDay` (both YYYY-MM-DD). */
export function daysBetween(fromDay: string, toDay: string): number {
  const toUtc = (day: string) => Date.parse(`${day.slice(0, 10)}T00:00:00Z`);
  return Math.round((toUtc(toDay) - toUtc(fromDay)) / 86_400_000);
}

export const STATUS_LABELS: Record<VehicleStatus, string> = {
  active: "Active",
  in_maintenance: "In maintenance",
  inactive: "Inactive",
};

export const TYPE_LABELS: Record<VehicleType, string> = {
  car: "Car",
  van: "Van",
  truck: "Truck",
  motorcycle: "Motorcycle",
};

export const MAINTENANCE_LABELS: Record<MaintenanceType, string> = {
  oil_change: "Oil change",
  tires: "Tires",
  brakes: "Brakes",
  inspection: "Inspection",
  repair: "Repair",
  other: "Other",
};
