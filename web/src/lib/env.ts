import "server-only";

// Server-side configuration. Read lazily (at request time, not at import or build time) so a
// build does not need the values, and a missing one fails loudly where it is used.

function required(name: "API_URL" | "DEMO_EMAIL" | "DEMO_PASSWORD"): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing environment variable ${name} (see web/.env.example)`);
  }
  return value;
}

/** Base URL of the fleet-manager API, without a trailing slash. */
export function apiUrl(): string {
  return required("API_URL").replace(/\/+$/, "");
}

export function demoCredentials(): { email: string; password: string } {
  return { email: required("DEMO_EMAIL"), password: required("DEMO_PASSWORD") };
}
