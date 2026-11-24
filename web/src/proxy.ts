import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/session";

// Optimistic routing on cookie presence only; the API still authorizes every call.
//
// - access cookie present          -> continue (and keep signed-in users away from /login)
// - only the refresh cookie        -> /session/resume, a page that refreshes the access token
//                                     in the browser while the "waking up" notice can show
//                                     (after 15 idle minutes the token is expired AND the
//                                     Render API is asleep, so this must not block here)
// - no cookies                     -> /login
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasAccess = request.cookies.has(ACCESS_COOKIE);
  const hasRefresh = request.cookies.has(REFRESH_COOKIE);
  const isPublic = pathname === "/login" || pathname === "/session/resume";

  if (hasAccess) {
    return isPublic ? NextResponse.redirect(new URL("/", request.url)) : NextResponse.next();
  }
  if (isPublic) {
    return NextResponse.next();
  }

  const target = hasRefresh ? "/session/resume" : "/login";
  const url = new URL(target, request.url);
  if (hasRefresh) {
    url.searchParams.set("next", `${pathname}${search}`);
  }
  return NextResponse.redirect(url);
}

export const config = {
  // Pages only: route handlers (/api/*) and static assets handle their own access.
  matcher: ["/((?!api/|_next/|favicon\\.ico|.*\\.(?:svg|png|jpg|ico|webp)$).*)"],
};
