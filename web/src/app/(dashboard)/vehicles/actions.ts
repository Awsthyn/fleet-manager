"use server";

import { redirect } from "next/navigation";

import type { VehicleFormState } from "@/components/vehicle-form";
import { ApiError, createVehicle, getCurrentUser, updateVehicle, type VehicleInput } from "@/lib/api";

function readInput(form: FormData): VehicleInput {
  const text = (key: string) => String(form.get(key) ?? "").trim();
  const driver = text("assigned_driver_id");
  return {
    plate: text("plate"),
    brand: text("brand"),
    model: text("model"),
    year: Number(text("year")),
    vehicle_type: text("vehicle_type"),
    status: text("status"),
    odometer_km: Number(text("odometer_km")),
    assigned_driver_id: driver ? Number(driver) : null,
  };
}

function describe(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Only admins can change vehicles.";
    return error.message;
  }
  throw error;
}

// Server Actions are reachable by direct POST, so each one re-checks the role itself. The API
// enforces it again on every write.
async function requireAdmin(): Promise<string | null> {
  const user = await getCurrentUser();
  return user.role === "admin" ? null : "Only admins can change vehicles.";
}

export async function createVehicleAction(
  _previous: VehicleFormState,
  form: FormData,
): Promise<VehicleFormState> {
  const denied = await requireAdmin();
  if (denied) return { error: denied };
  let id: number;
  try {
    id = (await createVehicle(readInput(form))).id;
  } catch (error) {
    return { error: describe(error) };
  }
  redirect(`/vehicles/${id}`);
}

export async function updateVehicleAction(
  vehicleId: number,
  _previous: VehicleFormState,
  form: FormData,
): Promise<VehicleFormState> {
  const denied = await requireAdmin();
  if (denied) return { error: denied };
  try {
    await updateVehicle(vehicleId, readInput(form));
  } catch (error) {
    return { error: describe(error) };
  }
  redirect(`/vehicles/${vehicleId}`);
}
