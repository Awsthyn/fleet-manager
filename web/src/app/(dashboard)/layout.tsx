import { LogOutIcon, TruckIcon } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { MainNav, NavLinks } from "@/components/main-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getCurrentUser } from "@/lib/api";

async function UserMenu() {
  const user = await getCurrentUser();
  return (
    <div className="flex items-center gap-2">
      <span className="hidden max-w-48 truncate text-sm text-muted-foreground sm:inline">
        {user.email}
      </span>
      <Badge variant="outline" className="capitalize">
        {user.role}
      </Badge>
      <form action="/api/auth/logout" method="post">
        <Button type="submit" variant="ghost" size="sm" aria-label="Sign out">
          <LogOutIcon aria-hidden="true" />
          <span className="hidden sm:inline">Sign out</span>
        </Button>
      </form>
    </div>
  );
}

export default function DashboardLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <TruckIcon className="size-4" aria-hidden="true" />
            </span>
            Fleet Manager
          </Link>
          <div className="ml-auto sm:order-last">
            <Suspense fallback={<Skeleton className="h-7 w-32" />}>
              <UserMenu />
            </Suspense>
          </div>
          <div className="w-full sm:w-auto">
            <Suspense fallback={<NavLinks pathname={null} />}>
              <MainNav />
            </Suspense>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
      <footer className="border-t py-4 text-center text-xs text-muted-foreground">
        Portfolio demo with fictional data.
      </footer>
    </div>
  );
}
