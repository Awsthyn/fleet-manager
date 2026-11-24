import { NextResponse, type NextRequest } from "next/server";

import { clearSessionCookies } from "@/lib/session";

function signedOut(request: NextRequest, reason?: string) {
  const url = new URL("/login", request.url);
  if (reason) url.searchParams.set("reason", reason);
  // 303: the browser follows with a GET even after a POST form submission.
  const response = NextResponse.redirect(url, 303);
  clearSessionCookies(response.cookies);
  return response;
}

/** Sign-out button (form POST). Tokens are stateless, so this clears the cookies. */
export async function POST(request: NextRequest) {
  return signedOut(request);
}

/** Used when the API rejects a token mid-render (Server Components cannot clear cookies). */
export async function GET(request: NextRequest) {
  const reason = request.nextUrl.searchParams.get("reason") === "expired" ? "expired" : undefined;
  return signedOut(request, reason);
}
