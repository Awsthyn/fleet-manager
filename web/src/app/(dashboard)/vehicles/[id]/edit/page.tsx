import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { VehicleForm } from "@/components/vehicle-form";
import { ApiError, getCurrentUser, getVehicle, listDrivers } from "@/lib/api";

import { updateVehicleAction } from "../../actions";

export const metadata: Metadata = { title: "Edit vehicle" };

async function EditVehicleContent({ params }: { params: PageProps<"/vehicles/[id]/edit">["params"] }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id < 1) notFound();
  const user = await getCurrentUser();
  if (user.role !== "admin") notFound();

  const [vehicle, drivers] = await Promise.all([
    getVehicle(id).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) notFound();
      throw error;
    }),
    listDrivers(),
  ]);
  return (
    <>
      <PageHeader title={`Edit ${vehicle.plate}`} />
      <VehicleForm
        action={updateVehicleAction.bind(null, vehicle.id)}
        drivers={drivers.items.filter(
          (d) => d.is_active || d.id === vehicle.assigned_driver?.id,
        )}
        vehicle={vehicle}
        cancelHref={`/vehicles/${vehicle.id}`}
      />
    </>
  );
}

export default function EditVehiclePage({ params }: PageProps<"/vehicles/[id]/edit">) {
  return (
    <Suspense fallback={<Skeleton className="h-96 max-w-2xl" />}>
      <EditVehicleContent params={params} />
    </Suspense>
  );
}
