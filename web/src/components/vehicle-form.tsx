"use client";

import { Loader2Icon } from "lucide-react";
import Link from "next/link";
import { useActionState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { STATUS_LABELS, TYPE_LABELS } from "@/lib/format";
import {
  VEHICLE_STATUSES,
  VEHICLE_TYPES,
  type Driver,
  type Vehicle,
} from "@/lib/types";

export type VehicleFormState = { error: string | null };
type Action = (state: VehicleFormState, form: FormData) => Promise<VehicleFormState>;

const MAX_YEAR = new Date().getFullYear() + 1;

export function VehicleForm({
  action,
  drivers,
  vehicle,
  cancelHref,
}: {
  action: Action;
  drivers: Driver[];
  vehicle?: Vehicle;
  cancelHref: string;
}) {
  const [state, formAction, pending] = useActionState(action, { error: null });

  return (
    <form action={formAction} className="grid max-w-2xl gap-4 sm:grid-cols-2">
      {state.error ? (
        <Alert variant="destructive" className="sm:col-span-2">
          <AlertDescription>{state.error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="plate">Plate</Label>
        <Input
          id="plate"
          name="plate"
          required
          defaultValue={vehicle?.plate}
          placeholder="ZZ123AB"
          autoCapitalize="characters"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="vehicle_type">Type</Label>
        <NativeSelect
          id="vehicle_type"
          name="vehicle_type"
          defaultValue={vehicle?.vehicle_type ?? "car"}
          className="w-full"
        >
          {VEHICLE_TYPES.map((type) => (
            <NativeSelectOption key={type} value={type}>
              {TYPE_LABELS[type]}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="brand">Brand</Label>
        <Input id="brand" name="brand" required maxLength={60} defaultValue={vehicle?.brand} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="model">Model</Label>
        <Input id="model" name="model" required maxLength={60} defaultValue={vehicle?.model} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="year">Year</Label>
        <Input
          id="year"
          name="year"
          type="number"
          required
          min={1980}
          max={MAX_YEAR}
          defaultValue={vehicle?.year ?? new Date().getFullYear()}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="odometer_km">Odometer (km)</Label>
        <Input
          id="odometer_km"
          name="odometer_km"
          type="number"
          required
          min={0}
          max={5_000_000}
          defaultValue={vehicle?.odometer_km ?? 0}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="status">Status</Label>
        <NativeSelect
          id="status"
          name="status"
          defaultValue={vehicle?.status ?? "active"}
          className="w-full"
        >
          {VEHICLE_STATUSES.map((status) => (
            <NativeSelectOption key={status} value={status}>
              {STATUS_LABELS[status]}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="assigned_driver_id">Driver</Label>
        <NativeSelect
          id="assigned_driver_id"
          name="assigned_driver_id"
          defaultValue={vehicle?.assigned_driver?.id.toString() ?? ""}
          className="w-full"
        >
          <NativeSelectOption value="">Unassigned</NativeSelectOption>
          {drivers.map((driver) => (
            <NativeSelectOption key={driver.id} value={driver.id}>
              {driver.full_name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" disabled={pending}>
          {pending ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : null}
          {vehicle ? "Save changes" : "Create vehicle"}
        </Button>
        <Link href={cancelHref} className={buttonVariants({ variant: "ghost" })}>
          Cancel
        </Link>
      </div>
    </form>
  );
}
