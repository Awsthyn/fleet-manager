import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WAKING_UP_MESSAGE, WakeGate } from "@/components/wake-gate";

/** A fetch whose response arrives only when the test calls `respond`. */
function deferredFetch() {
  let respond: (ok: boolean) => void = () => {};
  const fetchMock = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        respond = (ok) => resolve(new Response(null, { status: ok ? 200 : 503 }));
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, respond: (ok: boolean) => respond(ok) };
}

describe("WakeGate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows the waking-up notice while a slow /health is pending, then hides it", async () => {
    // Guards the cold-start UX: rejects a silent, broken-looking page while Render wakes up.
    const { fetchMock, respond } = deferredFetch();
    render(<WakeGate slowAfterMs={1500} />);

    expect(fetchMock).toHaveBeenCalledWith("/api/health", { cache: "no-store" });
    expect(screen.queryByText(WAKING_UP_MESSAGE)).not.toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(1500));
    expect(screen.getByRole("status")).toHaveTextContent(WAKING_UP_MESSAGE);

    await act(async () => respond(true));
    expect(screen.queryByText(WAKING_UP_MESSAGE)).not.toBeInTheDocument();
  });

  it("never shows the notice when /health answers quickly", async () => {
    // Guards against noise: rejects flashing the notice on every load of a warm server.
    const { respond } = deferredFetch();
    render(<WakeGate slowAfterMs={1500} />);

    await act(() => vi.advanceTimersByTimeAsync(200));
    await act(async () => respond(true));
    await act(() => vi.advanceTimersByTimeAsync(5000));

    expect(screen.queryByText(WAKING_UP_MESSAGE)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers a retry when the API does not answer", async () => {
    // Guards the failure path: rejects an endless spinner when the API is down.
    const { respond } = deferredFetch();
    render(<WakeGate slowAfterMs={1500} />);

    await act(() => vi.advanceTimersByTimeAsync(1500));
    await act(async () => respond(false));

    expect(screen.getByRole("alert")).toHaveTextContent("The API is not responding.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
