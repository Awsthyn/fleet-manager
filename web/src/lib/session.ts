import "server-only";

import type { NextResponse } from "next/server";

import { apiUrl } from "@/lib/env";

type ResponseCookies = NextResponse["cookies"];

// Tokens live only in httpOnly cookies: browser JavaScript can never read them. Every API call
// is made by the Next.js server, which reads the cookies and sends the bearer token itself.

export const ACCESS_COOKIE = "fm_access";
export const REFRESH_COOKIE = "fm_refresh";

// Drop the access cookie a little before the token expires, so a request never carries a token
// that expires in flight. Its absence (with a refresh cookie present) triggers a refresh.
const EXPIRY_MARGIN_SECONDS = 30;

// The API is on Render Free and may need up to a minute to wake up.
export const API_TIMEOUT_MS = 90_000;

type CookieOptions = Parameters<ResponseCookies["set"]>[2];

function cookieOptions(maxAgeSeconds: number): CookieOptions {
  return {
    httpOnly: true,
    // Secure everywhere except `next dev` on http://localhost.
    secure: process.env.NODE_ENV !== "development",
    sameSite: "lax",
    path: "/",
    maxAge: Math.max(maxAgeSeconds, 0),
  };
}

export function setAccessCookie(cookies: ResponseCookies, token: string, expiresIn: number) {
  cookies.set(ACCESS_COOKIE, token, cookieOptions(expiresIn - EXPIRY_MARGIN_SECONDS));
}

export function setSessionCookies(cookies: ResponseCookies, tokens: TokenPair) {
  setAccessCookie(cookies, tokens.access_token, tokens.expires_in);
  cookies.set(REFRESH_COOKIE, tokens.refresh_token, cookieOptions(tokens.refresh_expires_in));
}

export function clearSessionCookies(cookies: ResponseCookies) {
  cookies.delete(ACCESS_COOKIE);
  cookies.delete(REFRESH_COOKIE);
}

export type TokenPair = {
  access_token: string;
  expires_in: number;
  refresh_token: string;
  refresh_expires_in: number;
};

export type LoginResult =
  | { ok: true; tokens: TokenPair }
  | { ok: false; status: number; message: string };

/** Exchange credentials for a token pair at the API (OAuth2 password form). */
export async function loginAtApi(email: string, password: string): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl()}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
      cache: "no-store",
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });
  } catch {
    return { ok: false, status: 503, message: "The API did not respond. Try again in a moment." };
  }
  if (response.ok) {
    return { ok: true, tokens: (await response.json()) as TokenPair };
  }
  if (response.status === 401) {
    return { ok: false, status: 401, message: "Invalid email or password." };
  }
  if (response.status === 429) {
    return { ok: false, status: 429, message: "Too many login attempts. Wait a minute." };
  }
  return { ok: false, status: 502, message: "Login failed. Try again in a moment." };
}

export type RefreshResult =
  | { ok: true; accessToken: string; expiresIn: number }
  | { ok: false; status: number };

/** Get a new access token. `status: 401` means the refresh token is no longer valid. */
export async function refreshAtApi(refreshToken: string): Promise<RefreshResult> {
  try {
    const response = await fetch(`${apiUrl()}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });
    if (!response.ok) {
      return { ok: false, status: response.status === 401 ? 401 : 502 };
    }
    const body = (await response.json()) as { access_token: string; expires_in: number };
    return { ok: true, accessToken: body.access_token, expiresIn: body.expires_in };
  } catch {
    return { ok: false, status: 503 };
  }
}
