# fleet-manager

Fleet management REST API built with FastAPI, with a Next.js dashboard, deployed at zero cost.

## Run locally

Requires [uv](https://docs.astral.sh/uv/). uv installs the pinned Python version (see `.python-version`) automatically.

```bash
# Install runtime and development dependencies into .venv
uv sync

# Optional: create a local config (every variable has a development default)
cp .env.example .env

# Start the API with auto-reload
uv run uvicorn app.main:app --reload
```

The API is then available at http://127.0.0.1:8000, with interactive docs at http://127.0.0.1:8000/docs and a liveness check at http://127.0.0.1:8000/health.

Checks run by CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```
