"use client";

import { Loader2Icon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

/** Only same-site paths: never redirect to another origin from a query parameter. */
function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

/**
 * Reached when the access token expired but the refresh token is still valid (see proxy.ts).
 * Refreshing from the browser lets the "waking up" notice show while the API cold-starts.
 */
export function ResumeSession() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/refresh", { method: "POST" })
      .then((response) => {
        if (cancelled) return;
        router.replace(response.ok ? next : "/login?reason=expired");
        router.refresh();
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [next, router]);

  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
      <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
      Restoring your session…
    </p>
  );
}
