"use client";

import { Loader2Icon, TriangleAlertIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

export const WAKING_UP_MESSAGE = "Waking up the free-tier server, this can take up to a minute…";

type State = "checking" | "slow" | "ready" | "failed";

/**
 * Pings the API through /api/health when the app loads. If the answer takes longer than
 * `slowAfterMs` (the API on Render Free sleeps when idle), shows a notice instead of leaving the
 * user in front of a page that seems broken. Renders nothing when the API answers quickly.
 */
export function WakeGate({ slowAfterMs = 1500 }: { slowAfterMs?: number }) {
  const [state, setState] = useState<State>("checking");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) setState("slow");
    }, slowAfterMs);

    fetch("/api/health", { cache: "no-store" })
      .then((response) => setState(response.ok ? "ready" : "failed"))
      .catch(() => setState("failed"))
      .finally(() => {
        settled = true;
        clearTimeout(timer);
      });

    return () => {
      settled = true;
      clearTimeout(timer);
    };
  }, [slowAfterMs, attempt]);

  const retry = useCallback(() => {
    setState("checking");
    setAttempt((n) => n + 1);
  }, []);

  if (state === "slow") {
    return (
      <div
        role="status"
        className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-2 bg-amber-100 px-4 py-2 text-center text-sm text-amber-950 shadow-sm dark:bg-amber-900 dark:text-amber-50"
      >
        <Loader2Icon className="size-4 shrink-0 animate-spin" aria-hidden="true" />
        <span>{WAKING_UP_MESSAGE}</span>
      </div>
    );
  }
  if (state === "failed") {
    return (
      <div
        role="alert"
        className="fixed inset-x-0 top-0 z-50 flex flex-wrap items-center justify-center gap-2 bg-red-100 px-4 py-2 text-sm text-red-950 shadow-sm dark:bg-red-950 dark:text-red-50"
      >
        <TriangleAlertIcon className="size-4 shrink-0" aria-hidden="true" />
        <span>The API is not responding.</span>
        <Button size="xs" variant="outline" onClick={retry}>
          Retry
        </Button>
      </div>
    );
  }
  return null;
}
