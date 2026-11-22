# CLAUDE.md — fleet-manager

Portfolio project: a fleet management REST API (Python/FastAPI) with a Next.js dashboard, deployed at zero cost (Render Free + Neon Free + Vercel Hobby).

**Language:** all code, comments, commit messages and documentation are written in English.

## Stack

- **Backend:** Python 3.12+, managed with `uv`.
- **Web framework:** FastAPI.
- **Validation / schemas:** Pydantic v2.
- **Configuration:** pydantic-settings.
- **ORM:** SQLAlchemy 2.0 async, declarative `Mapped[...]` / `mapped_column()` style, with the `asyncpg` driver.
- **Migrations:** Alembic.
- **Tests:** pytest + pytest-asyncio + httpx (`AsyncClient` against the ASGI app).
- **Lint / format:** Ruff (both `ruff check` and `ruff format`).
- **Type checking:** pyright in `strict` mode.
- **Frontend:** Next.js (App Router, TypeScript) in `/web`.

## Architecture

Layered, with dependencies pointing one way only:

```
routers (HTTP)  ->  services (business logic)  ->  repositories (data access)
```

- **Routers** handle HTTP concerns only: parsing input, calling a service, mapping results and errors to responses. Routers never touch the DB session directly.
- **Services** hold business logic and orchestrate repositories. They know nothing about HTTP.
- **Repositories** are the only layer that runs queries against the database session.

## Code rules

- Type hints everywhere: function parameters, return types, and attributes.
- No `Any`, unless it is justified in a comment right next to it.
- Every behavior change ships with its tests **in the same commit**.
- Never delete or weaken a test to make it pass. If a test is wrong, explain why before changing it.

## Configuration and secrets

- Configuration comes **only** from environment variables, loaded through pydantic-settings.
- `.env.example` lists every variable with fake placeholder values and is kept up to date.
- `.env` is in `.gitignore`. Secrets are never committed.

## Data

- Fictional data only (seeds, fixtures, examples, screenshots). No real people, plates, companies or locations tied to real entities.

## Definition of done

Before calling any task finished, run all of these and show the commands together with their **actual** output:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

All four must be green. Do not summarize or paraphrase results — show what was actually printed.

## Deployment constraints

- **Render Free (API):**
  - 512 MB RAM — keep memory usage low (few workers, no heavy in-process caches).
  - Ephemeral disk — nothing written to the local filesystem survives a restart or redeploy.
  - The service sleeps after 15 minutes without traffic — expect cold starts.
  - No pre-deploy command — migrations must run some other way (e.g. as part of the start command or manually).
- **Neon Free (PostgreSQL):**
  - 1 GB storage.
  - Compute suspends after 5 minutes of inactivity — expect a slow first connection; connection handling must tolerate it.
  - Use the **pooled** connection URL for the application and the **direct** connection URL for Alembic.
- **Vercel Hobby:** hosts the Next.js dashboard in `/web`.
