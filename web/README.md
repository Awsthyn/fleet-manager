# fleet-manager web

Next.js dashboard for the fleet-manager API: overview metrics, vehicles and drivers, with a one-click read-only demo. Deployed on Vercel Hobby.

**Stack:** Next.js 16 (App Router, Cache Components, TypeScript strict), Tailwind CSS 4, shadcn/ui, Recharts, Vitest + Testing Library.

## Run locally

Requires Node 24+ and the API running (see the root README).

```bash
cd web
npm install
cp .env.example .env.local   # point API_URL at your API, set the demo credentials
npm run dev                  # http://localhost:3000
```

| Script | What it does |
|---|---|
| `npm run dev` | Development server |
| `npm run lint` | ESLint (Next.js config) |
| `npm run typecheck` | Generates route types, then `tsc --noEmit` |
| `npm test` | Vitest (jsdom) |
| `npm run build` | Production build |

## How it works

- **The browser never talks to the API.** Pages are Server Components that call the API from the Next.js server ([`src/lib/api.ts`](src/lib/api.ts)); forms use Server Actions.
- **Tokens live in httpOnly cookies** (`Secure`, `SameSite=Lax`), set by route handlers under `/api/auth/*`. Browser JavaScript cannot read them.
- **Refresh:** the access cookie expires slightly before the 15-minute token. [`src/proxy.ts`](src/proxy.ts) sends a request that only has the refresh cookie to `/session/resume`, which gets a new access token and returns to the page. This happens in the browser on purpose: after 15 idle minutes the token is expired *and* the Render API is asleep, so the wait needs to be visible.
- **Cold starts:** on every load, [`WakeGate`](src/components/wake-gate.tsx) pings `/api/health`. If the API takes more than 1.5 s, a "Waking up the free-tier server…" notice appears until it answers, with a retry if it fails.
- **Roles:** create and edit controls render only for admins. The API enforces roles on every write regardless.

## Environment variables

All server-side only (see [`.env.example`](.env.example)):

| Variable | Purpose |
|---|---|
| `API_URL` | Base URL of the API, e.g. `https://<service>.onrender.com` |
| `DEMO_EMAIL` | Read-only demo user for "Try the demo" |
| `DEMO_PASSWORD` | Its password |

## Deploy (Vercel)

Import the repository in Vercel with **Root Directory `web`**, set the three variables, deploy. Then add the Vercel URL to the API's `CORS_ORIGINS` on Render (only needed if something calls the API from a browser; the dashboard itself calls it server-side).
