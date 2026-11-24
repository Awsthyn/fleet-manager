import { PencilIcon, PlusIcon } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TYPE_LABELS, formatKm } from "@/lib/format";
import type { Vehicle } from "@/lib/types";

/** "New vehicle" for admins; viewers get nothing (the API would answer 403 anyway). */
export function NewVehicleButton({ canEdit }: { canEdit: boolean }) {
  if (!canEdit) return null;
  return (
    <Link href="/vehicles/new" className={buttonVariants()}>
      <PlusIcon aria-hidden="true" />
      New vehicle
    </Link>
  );
}

export function VehiclesTable({ vehicles, canEdit }: { vehicles: Vehicle[]; canEdit: boolean }) {
  if (vehicles.length === 0) {
    return (
      <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        No vehicles match these filters.
      </p>
    );
  }
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Plate</TableHead>
            <TableHead>Vehicle</TableHead>
            <TableHead className="hidden md:table-cell">Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="hidden text-right sm:table-cell">Odometer</TableHead>
            <TableHead className="hidden lg:table-cell">Driver</TableHead>
            {canEdit ? <TableHead className="w-0" aria-label="Actions" /> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {vehicles.map((vehicle) => (
            <TableRow key={vehicle.id}>
              <TableCell className="font-medium">
                <Link href={`/vehicles/${vehicle.id}`} className="hover:underline">
                  {vehicle.plate}
                </Link>
              </TableCell>
              <TableCell>
                <span className="block max-w-32 truncate sm:max-w-none">
                  {vehicle.brand} {vehicle.model}
                </span>
                <span className="text-xs text-muted-foreground">{vehicle.year}</span>
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {TYPE_LABELS[vehicle.vehicle_type]}
              </TableCell>
              <TableCell>
                <StatusBadge status={vehicle.status} />
              </TableCell>
              <TableCell className="hidden text-right tabular-nums sm:table-cell">
                {formatKm(vehicle.odometer_km)}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {vehicle.assigned_driver?.full_name ?? (
                  <span className="text-muted-foreground">Unassigned</span>
                )}
              </TableCell>
              {canEdit ? (
                <TableCell>
                  <Link
                    href={`/vehicles/${vehicle.id}/edit`}
                    className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
                    aria-label={`Edit ${vehicle.plate}`}
                  >
                    <PencilIcon aria-hidden="true" />
                  </Link>
                </TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
