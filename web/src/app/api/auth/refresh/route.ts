import { NextResponse, type NextRequest } from "next/server";

import {
  REFRESH_COOKIE,
  clearSessionCookies,
  refreshAtApi,
  setAccessCookie,
} from "@/lib/session";

/** New access token from the refresh cookie (called by /session/resume). */
export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  }

  const result = await refreshAtApi(refreshToken);
  if (!result.ok) {
    const response = NextResponse.json(
      { error: result.status === 401 ? "Session expired." : "The API did not respond." },
      { status: result.status },
    );
    if (result.status === 401) {
      clearSessionCookies(response.cookies);
    }
    return response;
  }
  const response = NextResponse.json({ ok: true });
  setAccessCookie(response.cookies, result.accessToken, result.expiresIn);
  return response;
}
