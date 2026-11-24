# API reference

Interactive documentation: `/docs` on the running API ([live](https://fleet-manager-api-01nn.onrender.com/docs)).

## Authentication

Every `/api/v1` resource requires a bearer token; only `/health`, `/docs`, `/openapi.json` and the login/refresh endpoints are public.

- `POST /api/v1/auth/login` (OAuth2 password flow: form fields `username` = email and `password`) returns a 15-minute access token and a 7-day refresh token. In `/docs`, use the **Authorize** button.
- `POST /api/v1/auth/refresh` with `{"refresh_token": "..."}` returns a new access token.
- `GET /api/v1/auth/me` returns the current user.

| Role | Can do |
|---|---|
| `viewer` | `GET` on every resource |
| `admin` | everything |

The seed script creates `demo@fleet.dev` (viewer, password from `DEMO_PASSWORD`) and an admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). Passwords are hashed with Argon2 and never stored in the repository. Login is limited to 10 failed attempts per minute per client IP (kept in process memory, which is enough for a single Render Free instance). Successful logins do not count, so the dashboard's server, which signs in every demo visitor from the same address, is not throttled; each attempt still reserves a slot while it is checked, so a burst of concurrent guesses cannot get past the limit. Deactivating a user invalidates their outstanding tokens; tokens are otherwise stateless, so there is no per-token logout.

## Resources

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

## Metrics

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
