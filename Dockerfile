# syntax=docker/dockerfile:1

# Both stages use the same base image, so the virtualenv built in the first one points at the
# same Python interpreter path in the second.
ARG PYTHON_IMAGE=python:3.12-slim

# --- Build stage: install runtime dependencies (no dev group) into /app/.venv -----------------
FROM ${PYTHON_IMAGE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Only the lockfile is needed here, so this layer stays cached until dependencies change.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# --- Runtime stage: interpreter, virtualenv and application code; no uv, no build tools -------
FROM ${PYTHON_IMAGE} AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production \
    PORT=8000

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
# Precompile the app's own code: less work on every cold start (Render Free sleeps when idle).
RUN python -m compileall -q app migrations

# Code stays owned by root and read-only for the process.
USER app

EXPOSE 8000
CMD ["python", "-m", "app.scripts.start"]
