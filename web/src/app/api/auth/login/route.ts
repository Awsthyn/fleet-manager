import { NextResponse, type NextRequest } from "next/server";

import { loginAtApi, setSessionCookies } from "@/lib/session";

/** Email/password login: the API's tokens end up in httpOnly cookies, never in the response. */
export async function POST(request: NextRequest) {
  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!email || !password) {
    return NextResponse.json({ error: "Enter your email and password." }, { status: 400 });
  }

  const result = await loginAtApi(email, password);
  if (!result.ok) {
    return NextResponse.json({ error: result.message }, { status: result.status });
  }
  const response = NextResponse.json({ ok: true });
  setSessionCookies(response.cookies, result.tokens);
  return response;
}
