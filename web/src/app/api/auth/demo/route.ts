import { NextResponse } from "next/server";

import { demoCredentials } from "@/lib/env";
import { loginAtApi, setSessionCookies } from "@/lib/session";

/** "Try the demo": signs in as the read-only viewer with credentials from server env vars. */
export async function POST() {
  const { email, password } = demoCredentials();
  const result = await loginAtApi(email, password);
  if (!result.ok) {
    const message =
      result.status === 401 ? "The demo account is not available right now." : result.message;
    return NextResponse.json({ error: message }, { status: result.status });
  }
  const response = NextResponse.json({ ok: true });
  setSessionCookies(response.cookies, result.tokens);
  return response;
}
