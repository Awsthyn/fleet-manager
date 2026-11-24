"use client";

import { CarFrontIcon, LayoutDashboardIcon, UsersIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Overview", icon: LayoutDashboardIcon },
  { href: "/vehicles", label: "Vehicles", icon: CarFrontIcon },
  { href: "/drivers", label: "Drivers", icon: UsersIcon },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Current page highlighted. Reads the URL, so it sits behind <Suspense> (see NavLinks). */
export function MainNav() {
  return <NavLinks pathname={usePathname()} />;
}

/** The links themselves; with `pathname` null (Suspense fallback) nothing is highlighted. */
export function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Main" className="flex gap-1 overflow-x-auto">
      {LINKS.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname !== null && isActive(pathname, href) ? "page" : undefined}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
            "aria-[current=page]:bg-muted aria-[current=page]:text-foreground",
          )}
        >
          <Icon className="size-4" aria-hidden="true" />
          {label}
        </Link>
      ))}
    </nav>
  );
}
