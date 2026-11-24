import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { VehicleForm } from "@/components/vehicle-form";
import { getCurrentUser, listDrivers } from "@/lib/api";

import { createVehicleAction } from "../actions";

export const metadata: Metadata = { title: "New vehicle" };

async function NewVehicleContent() {
  const user = await getCurrentUser();
  if (user.role !== "admin") notFound();
  const drivers = await listDrivers();
  return (
    <VehicleForm
      action={createVehicleAction}
      drivers={drivers.items.filter((d) => d.is_active)}
      cancelHref="/vehicles"
    />
  );
}

export default function NewVehiclePage() {
  return (
    <>
      <PageHeader title="New vehicle" />
      <Suspense fallback={<Skeleton className="h-96 max-w-2xl" />}>
        <NewVehicleContent />
      </Suspense>
    </>
  );
}
