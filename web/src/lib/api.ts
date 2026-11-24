import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { apiUrl } from "@/lib/env";
import { ACCESS_COOKIE, API_TIMEOUT_MS } from "@/lib/session";
import type {
  CurrentUser,
  Driver,
  MonthlyCostsResponse,
  Page,
  Summary,
  UpcomingMaintenanceResponse,
  Vehicle,
  VehicleDetail,
} from "@/lib/types";

// Data access layer: the only module that calls the API on behalf of a signed-in user. It runs
// on the Next.js server and reads the access token from its httpOnly cookie. proxy.ts makes sure
// a fresh access token is present before any page renders.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    return body.error?.message ?? `API error ${response.status}`;
  } catch {
    return `API error ${response.status}`;
  }
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) {
    redirect("/login");
  }
  const response = await fetch(`${apiUrl()}/api/v1${path}`, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(API_TIMEOUT_MS),
  });
  if (response.status === 401) {
    // Revoked or otherwise rejected token: end the session (cookies are cleared there).
    redirect("/api/auth/logout?reason=expired");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/** The signed-in user; one API call per request however many components ask. */
export const getCurrentUser = cache(async (): Promise<CurrentUser> => {
  const user = await apiFetch<CurrentUser & Record<string, unknown>>("/auth/me");
  return { id: user.id, email: user.email, role: user.role };
});

export function getSummary(): Promise<Summary> {
  return apiFetch("/metrics/summary");
}

export function getUpcomingMaintenance(days = 30): Promise<UpcomingMaintenanceResponse> {
  return apiFetch(`/metrics/maintenance/upcoming${query({ days })}`);
}

export function getMonthlyCosts(months = 6): Promise<MonthlyCostsResponse> {
  return apiFetch(`/metrics/costs/monthly${query({ months })}`);
}

export type VehicleFilters = { status?: string; q?: string; limit: number; offset: number };

export function listVehicles(filters: VehicleFilters): Promise<Page<Vehicle>> {
  return apiFetch(`/vehicles${query(filters)}`);
}

export function getVehicle(id: number): Promise<VehicleDetail> {
  return apiFetch(`/vehicles/${id}`);
}

export function listDrivers(limit = 100): Promise<Page<Driver>> {
  return apiFetch(`/drivers${query({ limit })}`);
}

export type VehicleInput = {
  plate: string;
  brand: string;
  model: string;
  year: number;
  vehicle_type: string;
  status: string;
  odometer_km: number;
  assigned_driver_id: number | null;
};

export function createVehicle(input: VehicleInput): Promise<Vehicle> {
  return apiFetch("/vehicles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function updateVehicle(id: number, input: VehicleInput): Promise<Vehicle> {
  return apiFetch(`/vehicles/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
