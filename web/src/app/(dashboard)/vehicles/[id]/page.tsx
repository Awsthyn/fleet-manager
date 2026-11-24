import type { Metadata } from "next";
import { ArrowLeftIcon, PencilIcon } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { StatusBadge } from "@/components/status-badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, getCurrentUser, getVehicle } from "@/lib/api";
import {
  MAINTENANCE_LABELS,
  TYPE_LABELS,
  formatDate,
  formatKm,
  formatMoney,
} from "@/lib/format";
import type { VehicleDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Vehicle" };

async function loadVehicle(rawId: string): Promise<VehicleDetail> {
  const id = Number(rawId);
  if (!Number.isInteger(id) || id < 1) notFound();
  try {
    return await getVehicle(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}

async function VehicleContent({ params }: { params: PageProps<"/vehicles/[id]">["params"] }) {
  const { id } = await params;
  const [vehicle, user] = await Promise.all([loadVehicle(id), getCurrentUser()]);
  const driver = vehicle.assigned_driver;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
            {vehicle.plate}
            <StatusBadge status={vehicle.status} />
          </h1>
          <p className="text-sm text-muted-foreground">
            {vehicle.brand} {vehicle.model} · {vehicle.year}
          </p>
        </div>
        {user.role === "admin" ? (
          <Link href={`/vehicles/${vehicle.id}/edit`} className={buttonVariants({ variant: "outline" })}>
            <PencilIcon aria-hidden="true" />
            Edit
          </Link>
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Vehicle</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4">
              <Field label="Type">{TYPE_LABELS[vehicle.vehicle_type]}</Field>
              <Field label="Odometer">{formatKm(vehicle.odometer_km)}</Field>
              <Field label="Brand">{vehicle.brand}</Field>
              <Field label="Model">{vehicle.model}</Field>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Assigned driver</CardTitle>
          </CardHeader>
          <CardContent>
            {driver ? (
              <dl className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <Field label="Name">{driver.full_name}</Field>
                </div>
                <Field label="License">{driver.license_number}</Field>
                <Field label="License expiry">{formatDate(driver.license_expiry)}</Field>
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">No driver assigned.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Recent maintenance</CardTitle>
          <CardDescription>The five most recent records</CardDescription>
        </CardHeader>
        <CardContent>
          {vehicle.recent_maintenance.length === 0 ? (
            <p className="text-sm text-muted-foreground">No maintenance recorded yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">Odometer</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="hidden md:table-cell">Next due</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vehicle.recent_maintenance.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(record.performed_at)}
                    </TableCell>
                    <TableCell>
                      {MAINTENANCE_LABELS[record.maintenance_type]}
                      {record.notes ? (
                        <span className="block max-w-56 truncate text-xs text-muted-foreground">
                          {record.notes}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums sm:table-cell">
                      {formatKm(record.odometer_km)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(record.cost)}
                    </TableCell>
                    <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                      {[
                        record.next_due_date ? formatDate(record.next_due_date) : null,
                        record.next_due_km !== null ? formatKm(record.next_due_km) : null,
                      ]
                        .filter(Boolean)
                        .join(" or ") || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}

export default function VehiclePage({ params }: PageProps<"/vehicles/[id]">) {
  return (
    <>
      <Link
        href="/vehicles"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" aria-hidden="true" />
        Vehicles
      </Link>
      <Suspense
        fallback={
          <div className="flex flex-col gap-4">
            <Skeleton className="h-12 w-56" />
            <div className="grid gap-4 md:grid-cols-2">
              <Skeleton className="h-40" />
              <Skeleton className="h-40" />
            </div>
            <Skeleton className="h-64" />
          </div>
        }
      >
        <VehicleContent params={params} />
      </Suspense>
    </>
  );
}
