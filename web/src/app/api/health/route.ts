import { NextResponse } from "next/server";

import { apiUrl } from "@/lib/env";
import { API_TIMEOUT_MS } from "@/lib/session";

/** Pings the API's /health, waiting as long as a cold start takes (used by WakeGate). */
export async function GET() {
  try {
    const response = await fetch(`${apiUrl()}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });
    return NextResponse.json({ ok: response.ok }, { status: response.ok ? 200 : 502 });
  } catch {
    return NextResponse.json({ ok: false }, { status: 503 });
  }
}
