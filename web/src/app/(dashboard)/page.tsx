import type { Metadata } from "next";
import { CarFrontIcon, IdCardIcon, WrenchIcon, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { CostsChart } from "@/components/costs-chart";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getMonthlyCosts, getSummary, getUpcomingMaintenance } from "@/lib/api";
import { MAINTENANCE_LABELS, STATUS_LABELS, formatMoney } from "@/lib/format";
import { maintenanceReason } from "@/lib/maintenance";
import type { VehicleStatus } from "@/lib/types";

export const metadata: Metadata = { title: "Overview" };

function StatCard({
  title,
  value,
  detail,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: number;
  detail: string;
  icon: LucideIcon;
  tone?: "default" | "warning";
}) {
  return (
    <Card size="sm">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardDescription>{title}</CardDescription>
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        <p
          className={
            tone === "warning" && value > 0
              ? "text-3xl font-semibold text-amber-600 dark:text-amber-400"
              : "text-3xl font-semibold"
          }
        >
          {value}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}

async function SummaryCards() {
  const summary = await getSummary();
  const byStatus = (Object.keys(STATUS_LABELS) as VehicleStatus[])
    .map((status) => `${summary.vehicles.by_status[status]} ${STATUS_LABELS[status].toLowerCase()}`)
    .join(" · ");
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard title="Vehicles" value={summary.vehicles.total} detail={byStatus} icon={CarFrontIcon} />
      <StatCard
        title="Overdue maintenance"
        value={summary.maintenance.overdue}
        detail={`${summary.maintenance.vehicles_with_overdue} vehicles affected`}
        icon={WrenchIcon}
        tone="warning"
      />
      <StatCard
        title="Active drivers"
        value={summary.drivers.active}
        detail={`${summary.drivers.licenses_expired} with an expired license`}
        icon={IdCardIcon}
      />
      <StatCard
        title="Licenses expiring"
        value={summary.drivers.licenses_expiring_soon}
        detail="Within the next 30 days"
        icon={IdCardIcon}
        tone="warning"
      />
    </div>
  );
}

async function MonthlyCosts() {
  const costs = await getMonthlyCosts(6);
  return (
    <Card className="lg:col-span-3">
      <CardHeader>
        <CardTitle>Monthly costs</CardTitle>
        <CardDescription>
          Last 6 months: {formatMoney(costs.totals.maintenance)} maintenance,{" "}
          {formatMoney(costs.totals.fuel)} fuel
        </CardDescription>
      </CardHeader>
      <CardContent>
        <CostsChart months={costs.months} />
      </CardContent>
    </Card>
  );
}

async function UpcomingList() {
  const upcoming = await getUpcomingMaintenance(30);
  const items = upcoming.items.slice(0, 8);
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Maintenance due</CardTitle>
        <CardDescription>Overdue or due within {upcoming.days} days</CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing due. The fleet is up to date.</p>
        ) : (
          <ul className="divide-y">
            {items.map((item) => (
              <li
                key={`${item.vehicle_id}-${item.maintenance_type}`}
                className="flex items-start justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <Link
                    href={`/vehicles/${item.vehicle_id}`}
                    className="font-medium hover:underline"
                  >
                    {item.plate}
                  </Link>{" "}
                  <span className="text-sm text-muted-foreground">
                    {MAINTENANCE_LABELS[item.maintenance_type]}
                  </span>
                  <p className="truncate text-xs text-muted-foreground">
                    {maintenanceReason(item)}
                  </p>
                </div>
                <Badge
                  variant={item.state === "overdue" ? "destructive" : "secondary"}
                  className="shrink-0"
                >
                  {item.state === "overdue" ? "Overdue" : "Upcoming"}
                </Badge>
              </li>
            ))}
          </ul>
        )}
        {upcoming.items.length > items.length ? (
          <p className="mt-3 text-xs text-muted-foreground">
            And {upcoming.items.length - items.length} more.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  return (
    <>
      <PageHeader title="Overview" description="Fleet status at a glance." />
      <div className="flex flex-col gap-4">
        <Suspense
          fallback={
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          }
        >
          <SummaryCards />
        </Suspense>
        <div className="grid gap-4 lg:grid-cols-5">
          <Suspense fallback={<Skeleton className="h-96 lg:col-span-3" />}>
            <MonthlyCosts />
          </Suspense>
          <Suspense fallback={<Skeleton className="h-96 lg:col-span-2" />}>
            <UpcomingList />
          </Suspense>
        </div>
      </div>
    </>
  );
}
