import type { Metadata } from "next";
import { ChevronLeftIcon, ChevronRightIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { PageHeader } from "@/components/page-header";
import { NewVehicleButton, VehiclesTable } from "@/components/vehicles-table";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { getCurrentUser, listVehicles } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/format";
import { VEHICLE_STATUSES, type VehicleStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Vehicles" };

const PAGE_SIZE = 10;

type Filters = { status?: VehicleStatus; q?: string; page: number };

function parseFilters(params: Record<string, string | string[] | undefined>): Filters {
  const one = (key: string) => (typeof params[key] === "string" ? params[key] : undefined);
  const status = VEHICLE_STATUSES.find((s) => s === one("status"));
  const q = one("q")?.trim().slice(0, 60) || undefined;
  const page = Math.max(1, Number.parseInt(one("page") ?? "1", 10) || 1);
  return { status, q, page };
}

function pageHref(filters: Filters, page: number): string {
  const search = new URLSearchParams();
  if (filters.status) search.set("status", filters.status);
  if (filters.q) search.set("q", filters.q);
  if (page > 1) search.set("page", String(page));
  const text = search.toString();
  return text ? `/vehicles?${text}` : "/vehicles";
}

/** Plain GET form: filtering works without client-side JavaScript. */
function FilterBar({ filters }: { filters: Filters }) {
  return (
    <form method="get" className="mb-4 flex flex-wrap items-center gap-2" role="search">
      <div className="relative min-w-48 flex-1">
        <SearchIcon
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          name="q"
          defaultValue={filters.q}
          placeholder="Plate, brand or model"
          aria-label="Search vehicles"
          className="pl-8"
          maxLength={60}
        />
      </div>
      <NativeSelect name="status" defaultValue={filters.status ?? ""} aria-label="Status">
        <NativeSelectOption value="">All statuses</NativeSelectOption>
        {VEHICLE_STATUSES.map((status) => (
          <NativeSelectOption key={status} value={status}>
            {STATUS_LABELS[status]}
          </NativeSelectOption>
        ))}
      </NativeSelect>
      <Button type="submit" variant="secondary">
        Apply
      </Button>
      {filters.q || filters.status ? (
        <Link href="/vehicles" className={buttonVariants({ variant: "ghost" })}>
          Clear
        </Link>
      ) : null}
    </form>
  );
}

async function VehiclesContent({ searchParams }: { searchParams: PageProps<"/vehicles">["searchParams"] }) {
  const filters = parseFilters(await searchParams);
  const [user, page] = await Promise.all([
    getCurrentUser(),
    listVehicles({
      status: filters.status,
      q: filters.q,
      limit: PAGE_SIZE,
      offset: (filters.page - 1) * PAGE_SIZE,
    }),
  ]);
  const canEdit = user.role === "admin";
  const pages = Math.max(1, Math.ceil(page.total / PAGE_SIZE));
  const first = page.total === 0 ? 0 : page.offset + 1;
  const last = page.offset + page.items.length;

  return (
    <>
      <PageHeader
        title="Vehicles"
        description={`${page.total} vehicles`}
        actions={<NewVehicleButton canEdit={canEdit} />}
      />
      <FilterBar filters={filters} />
      <VehiclesTable vehicles={page.items} canEdit={canEdit} />
      <nav
        aria-label="Pagination"
        className="mt-4 flex items-center justify-between gap-2 text-sm text-muted-foreground"
      >
        <span>
          {first}–{last} of {page.total}
        </span>
        <div className="flex gap-2">
          <Link
            href={pageHref(filters, filters.page - 1)}
            aria-disabled={filters.page <= 1}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              filters.page <= 1 && "pointer-events-none opacity-50",
            )}
          >
            <ChevronLeftIcon aria-hidden="true" />
            Previous
          </Link>
          <Link
            href={pageHref(filters, filters.page + 1)}
            aria-disabled={filters.page >= pages}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              filters.page >= pages && "pointer-events-none opacity-50",
            )}
          >
            Next
            <ChevronRightIcon aria-hidden="true" />
          </Link>
        </div>
      </nav>
    </>
  );
}

export default function VehiclesPage({ searchParams }: PageProps<"/vehicles">) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-4">
          <Skeleton className="h-12 w-48" />
          <Skeleton className="h-9" />
          <Skeleton className="h-96" />
        </div>
      }
    >
      <VehiclesContent searchParams={searchParams} />
    </Suspense>
  );
}
