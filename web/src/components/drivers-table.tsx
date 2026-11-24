import { TriangleAlertIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { daysBetween, formatDate } from "@/lib/format";
import type { Driver } from "@/lib/types";

/** Same window the API's summary uses for "licenses expiring soon". */
export const EXPIRY_WINDOW_DAYS = 30;

export type LicenseState = "expired" | "expiring" | "valid";

export function licenseState(expiry: string, today: string): LicenseState {
  const days = daysBetween(today, expiry);
  if (days < 0) return "expired";
  if (days <= EXPIRY_WINDOW_DAYS) return "expiring";
  return "valid";
}

function LicenseBadge({ state, days }: { state: LicenseState; days: number }) {
  if (state === "expired") return <Badge variant="destructive">Expired</Badge>;
  if (state === "expiring") {
    return (
      <Badge className="bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200">
        {days === 0 ? "Expires today" : `Expires in ${days} days`}
      </Badge>
    );
  }
  return <Badge variant="secondary">Valid</Badge>;
}

export function DriversTable({ drivers, today }: { drivers: Driver[]; today: string }) {
  const alerts = drivers.filter(
    (d) => d.is_active && licenseState(d.license_expiry, today) !== "valid",
  );

  return (
    <div className="flex flex-col gap-4">
      {alerts.length > 0 ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
        >
          <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            <strong>
              {alerts.length} active {alerts.length === 1 ? "driver needs" : "drivers need"} a
              license renewal:
            </strong>{" "}
            {alerts.map((d) => d.full_name).join(", ")}.
          </p>
        </div>
      ) : null}
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="hidden sm:table-cell">License</TableHead>
              <TableHead>Expiry</TableHead>
              <TableHead className="hidden md:table-cell">Phone</TableHead>
              <TableHead className="hidden sm:table-cell">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {drivers.map((driver) => {
              const state = licenseState(driver.license_expiry, today);
              return (
                <TableRow key={driver.id} className={driver.is_active ? undefined : "opacity-60"}>
                  <TableCell className="font-medium">{driver.full_name}</TableCell>
                  <TableCell className="hidden font-mono text-xs sm:table-cell">
                    {driver.license_number}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col items-start gap-1">
                      <span className="whitespace-nowrap">{formatDate(driver.license_expiry)}</span>
                      <LicenseBadge state={state} days={daysBetween(today, driver.license_expiry)} />
                    </div>
                  </TableCell>
                  <TableCell className="hidden whitespace-nowrap md:table-cell">
                    {driver.phone}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {driver.is_active ? "Active" : "Inactive"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
