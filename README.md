# fleet-manager

[![CI](https://github.com/Awsthyn/fleet-manager/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Awsthyn/fleet-manager/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Awsthyn/fleet-manager/badges/coverage.json)](https://github.com/Awsthyn/fleet-manager/actions/workflows/ci.yml)

Fleet management REST API built with FastAPI, with a Next.js dashboard, deployed at zero cost.

## Run locally

Requires [uv](https://docs.astral.sh/uv/) and, for the local database and the test suite, Docker. uv installs the pinned Python version (see `.python-version`) automatically.

```bash
# Install runtime and development dependencies into .venv
uv sync

# Start a local PostgreSQL 18 (listens on 127.0.0.1:5433)
docker compose up -d db

# Optional: create a local config. Without DATABASE_URL / DATABASE_URL_DIRECT,
# the app uses the docker-compose database.
cp .env.example .env

# Create the schema and load fictional demo data
# (the seed needs DEMO_PASSWORD, ADMIN_EMAIL and ADMIN_PASSWORD, see .env.example)
uv run alembic upgrade head
uv run python -m app.scripts.seed

# Start the API with auto-reload
uv run uvicorn app.main:app --reload
```

The API is then available at http://127.0.0.1:8000, with interactive docs at http://127.0.0.1:8000/docs and a liveness check at http://127.0.0.1:8000/health.

## Dashboard

A Next.js dashboard in [`web/`](web/) (overview metrics and costs chart, vehicles, drivers, one-click read-only demo), deployed on Vercel Hobby. The browser never calls the API directly: the Next.js server does, with tokens kept in httpOnly cookies. Setup, scripts and design notes: [web/README.md](web/README.md).

## API

Interactive documentation lives at `/docs`.

### Authentication

Every `/api/v1` resource requires a bearer token; only `/health`, `/docs`, `/openapi.json` and the login/refresh endpoints are public.

- `POST /api/v1/auth/login` (OAuth2 password flow: form fields `username` = email and `password`) returns a 15-minute access token and a 7-day refresh token. In `/docs`, use the **Authorize** button.
- `POST /api/v1/auth/refresh` with `{"refresh_token": "..."}` returns a new access token.
- `GET /api/v1/auth/me` returns the current user.

| Role | Can do |
|---|---|
| `viewer` | `GET` on every resource |
| `admin` | everything |

The seed script creates `demo@fleet.dev` (viewer, password from `DEMO_PASSWORD`) and an admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). Passwords are hashed with Argon2 and never stored in the repository. Login is limited to 10 failed attempts per minute per client IP (kept in process memory, which is enough for a single Render Free instance). Successful logins do not count, so the dashboard's server, which signs in every demo visitor from the same address, is not throttled; each attempt still reserves a slot while it is checked, so a burst of concurrent guesses cannot get past the limit. Deactivating a user invalidates their outstanding tokens; tokens are otherwise stateless, so there is no per-token logout.

### Resources

Under `/api/v1`:

| Resource | Endpoints | List filters |
|---|---|---|
| `/vehicles` | list, create, get (with driver and 5 latest maintenance records), patch, delete | `status`, `vehicle_type`, `q` (plate/brand/model), `has_overdue_maintenance` |
| `/drivers` | list, create, get, patch, delete | `is_active`, `q` (name/license) |
| `/maintenance-records` | list, create, get, patch, delete | `vehicle_id`, `maintenance_type`, `performed_from`, `performed_to` |
| `/fuel-logs` | list, create, get, patch, delete | `vehicle_id`, `driver_id`, `filled_from`, `filled_to` |

- **Pagination:** `limit` (1-100, default 20) and `offset`; responses are `{"items", "total", "limit", "offset"}`.
- **Partial updates:** `PATCH` changes only the fields sent; `null` is accepted only for nullable fields (e.g. `assigned_driver_id: null` unassigns a driver).
- **Errors** always have the same body, `{"error": {"code", "message", "details"}}`: `404 not_found`, `409 conflict` (duplicate plate or license number), `422 validation_error` (malformed input, with per-field `details`) or `422 invalid_data` (well-formed input that breaks a rule, e.g. next service before this one).
- **Dates** in filters are calendar days in Argentina time (UTC-3). Money and liters are decimals serialized as strings.
- **Overdue maintenance:** for each vehicle and maintenance type, only the latest record counts; it is overdue when its `next_due_km` is below the vehicle's odometer or its `next_due_date` has passed.

### Metrics

Read-only, available to viewers, computed in PostgreSQL (`GROUP BY`, `FILTER`, `row_number()`, `LAG()`):

| Endpoint | Returns |
|---|---|
| `GET /api/v1/metrics/summary` | vehicles by status, active drivers, licenses expiring within 30 days (and already expired), overdue maintenance items and vehicles |
| `GET /api/v1/metrics/maintenance/upcoming?days=30` | overdue or upcoming maintenance, most urgent first, with the trigger (`date` or `km`) |
| `GET /api/v1/metrics/costs/monthly?months=6` | maintenance + fuel cost per calendar month (zero-filled), totals and the 5 most expensive vehicles |
| `GET /api/v1/metrics/fuel/efficiency` | km per liter per vehicle and for the fleet |

- **Km-based due dates** are turned into days using each vehicle's recent usage (km per day across its fuel logs of the last 90 days). Without enough fuel logs, a km trigger is listed only once reached.
- **Fuel efficiency** uses the full-tank method: the distance between two consecutive fills divided by the liters of the later one, weighted by distance. Fills where the odometer did not advance are ignored.
- **Months** are calendar months in Argentina time.

## Database

### Connection URLs

| Variable | Used by | On Neon |
|---|---|---|
| `DATABASE_URL` | the application | pooled endpoint ("Connection pooling" on, host contains `-pooler`) |
| `DATABASE_URL_DIRECT` | Alembic migrations | direct endpoint ("Connection pooling" off) |

Paste the URLs exactly as Neon shows them (`postgresql://...?sslmode=require&channel_binding=require`). The asyncpg driver does not accept libpq query parameters, so [app/db/url.py](app/db/url.py) adapts them at startup:

- the scheme becomes `postgresql+asyncpg://`;
- `sslmode` is removed from the URL and passed to asyncpg as its `ssl` argument (same mode names, so TLS stays enforced);
- `channel_binding` has no asyncpg equivalent and is dropped;
- on pooled hosts (PgBouncer in transaction mode), asyncpg's prepared-statement cache is disabled and statements get unique names, avoiding collisions between clients sharing a server connection.

Migrations go through the direct endpoint because DDL and Alembic's session-level state do not belong behind a transaction-mode pooler.

### Migrations

```bash
uv run alembic upgrade head                                 # apply all migrations
uv run alembic downgrade -1                                 # roll back the latest one
uv run alembic revision --autogenerate -m "describe change" # new migration from model changes
```

Always review an autogenerated migration before committing it. Autogenerate does not drop PostgreSQL enum types on downgrade, among other gaps; the initial migration documents what was fixed by hand. The test suite fails if the models and the migrations drift apart.

### Seed data

```bash
uv run python -m app.scripts.seed
```

Loads fictional data into `DATABASE_URL`: 25 vehicles, 12 drivers (some with licenses expiring within 30 days) and six months of maintenance records and fuel logs, with a few vehicles overdue for service. A fixed random seed makes the data reproducible; dates are relative to the day it runs. The script is idempotent: running it again inserts nothing new.

## Tests

The suite needs the docker-compose database (`docker compose up -d db`). It creates a separate `fleet_test` database, applies the Alembic migrations to it and runs each test inside a transaction that is rolled back afterwards. Set `TEST_DATABASE_URL` to use another server.

Checks run by CI (where PostgreSQL runs as a service container):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --cov            # coverage report per file; fails below 80 %
```

CI fails if total coverage (lines and branches) drops below 80 %, attaches the HTML and XML reports to each run as the `coverage-report` artifact, and on `main` publishes the figure shown in the coverage badge (a JSON file on the `badges` branch, rendered by shields.io). Coverage is measured with greenlet support (`[tool.coverage.run]` in `pyproject.toml`); without it, code that resumes after an async database call is under-reported.

## Development

Run Ruff automatically on every commit with [pre-commit](https://pre-commit.com/) (already a dev dependency):

```bash
uv run pre-commit install          # once per clone: adds the git hook
uv run pre-commit run --all-files  # optional: check the whole repository now
```

The hooks call the Ruff version pinned in `uv.lock`, so local commits and CI never disagree. When a hook fixes a file, the commit stops: review the changes, `git add` them and commit again.

## Logging

- **Format:** one JSON object per line when `ENV=production` (`timestamp`, `level`, `logger`, `message`, `request_id` and event fields); readable text otherwise.
- **Request ids:** every response carries an `X-Request-ID` header. A caller-supplied id (up to 64 characters of letters, digits, `.`, `_`, `-`) is reused; otherwise one is generated. All log lines of a request include it.
- **Access log:** one `request completed` line per request with method, path (never the query string), status and duration.
- **Unexpected errors:** the full traceback is logged; the client only gets `500` with `{"error": {"code": "internal_error", "message": "Internal server error"}}` and the request id to quote.

## Deploy

The API runs on [Render](https://render.com/) Free as a Docker web service, against the Neon Free database.

### How it works

- **Image** ([`Dockerfile`](Dockerfile)): multi-stage build. uv installs only the runtime dependencies from `uv.lock` in a build stage; the final `python:3.12-slim` image holds the interpreter, the virtualenv and the code, and runs as a non-root user. [`.dockerignore`](.dockerignore) is an allowlist, so `.env`, `.venv`, `.git` and tests never enter the build.
- **Start:** the container runs `python -m app.scripts.start`, which applies pending migrations (`alembic upgrade head`, on `DATABASE_URL_DIRECT`) and then starts uvicorn on `$PORT` (default 8000). Render Free has no pre-deploy command, so this happens on every start; when the schema is already current it is a no-op. **If the migration fails, the process exits with status 1 and the server never starts.**
- **CI:** every push and pull request also builds the image and starts it against an empty PostgreSQL, failing unless the migration runs and `/health` answers. A broken Dockerfile or entrypoint shows up in CI, not on Render.
- **Blueprint** ([`render.yaml`](render.yaml)): one free web service in Ohio (the same AWS region as the Neon database), health check on `/health`, auto-deploy after CI passes. Secret variables are declared with `sync: false`: Render asks for them on the first sync and they live only in its dashboard.

### First deploy

1. Render dashboard → **New → Blueprint** → select this repository. Confirm the plan is **Free**.
2. Fill in the prompted variables: `DATABASE_URL` (Neon pooled), `DATABASE_URL_DIRECT` (Neon direct), `JWT_SECRET` (a long random value, e.g. `uv run python -c "import secrets; print(secrets.token_hex(64))"`), `CORS_ORIGINS` (the dashboard origin, comma-separated) and the seed users' variables.
3. Deploy. The logs show the migration, then `Uvicorn running`.
4. Load the demo data once from a machine with the Neon URLs in `.env`: `uv run python -m app.scripts.seed` (idempotent).

### Run the image locally

```bash
docker compose up -d db
docker build -t fleet-manager-api .
docker run --rm -p 8000:8000 --network fleet-manager_default \
  -e DATABASE_URL=postgresql://fleet:fleet@db:5432/fleet \
  -e DATABASE_URL_DIRECT=postgresql://fleet:fleet@db:5432/fleet \
  -e JWT_SECRET=any-local-test-value \
  fleet-manager-api
curl http://127.0.0.1:8000/health
```

The image sets `ENV=production` (JSON logs, and a real `JWT_SECRET` is required).

### Free-tier limitations

- **Sleeps after 15 minutes without traffic.** The next request wakes it up. Measured on 2026-11-23 after 21 idle minutes: the first `GET /health` took **22.4 s** (warm: ~0.2-0.6 s), and the first login after that **3.0 s**, because Neon's compute also suspends after 5 idle minutes and Argon2 runs on a shared CPU. Render documents wake-ups of up to about a minute.
- **Ephemeral disk:** nothing written to the container's filesystem survives a restart or redeploy. All state lives in PostgreSQL.
- **750 free instance hours per month**, shared by every free service in the workspace. One service running all month uses about 744.
- **512 MB of RAM:** a single uvicorn worker (about 70 MB at idle).
- **Client IPs:** requests reach the app through Cloudflare and Render's internal load balancer, and Render appends to a client-supplied `X-Forwarded-For` instead of replacing it. Uvicorn therefore trusts only private networks and Cloudflare's published ranges ([`app/core/proxies.py`](app/core/proxies.py)) and takes the rightmost untrusted entry as the client, so a spoofed header cannot dodge the login rate limit. If Cloudflare adds ranges, the list needs updating; until then, affected clients share a rate-limit bucket rather than escaping it.
