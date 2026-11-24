import type { Metadata } from "next";
import { Suspense } from "react";

import { DriversTable } from "@/components/drivers-table";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { getSummary, listDrivers } from "@/lib/api";

export const metadata: Metadata = { title: "Drivers" };

async function DriversContent() {
  // The summary's as_of is the API's business day (Argentina time): license states use it
  // instead of this server's clock, so they match the overview counters.
  const [drivers, summary] = await Promise.all([listDrivers(), getSummary()]);
  return (
    <>
      <PageHeader
        title="Drivers"
        description={`${drivers.total} drivers · ${summary.drivers.active} active`}
      />
      <DriversTable drivers={drivers.items} today={summary.as_of} />
    </>
  );
}

export default function DriversPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-4">
          <Skeleton className="h-12 w-48" />
          <Skeleton className="h-96" />
        </div>
      }
    >
      <DriversContent />
    </Suspense>
  );
}
