# 0001: The backend is Python 3.13 with FastAPI, in three plain layers

- Status: accepted
- Date: 2026-11-13 ~18:45 (Europe/Helsinki)
- Decided by: Bogdan ("then also using python backend with fastapi etc clean arhitecutre, but nothing
  overgineered")
- Board thread: to be posted by the orchestrator

## Context

The challenge isn't picked yet (hacking starts Fri 19:30), but the backend stack can be fixed now so the team starts
from a working skeleton. The frontend and any database are still open.

## Decision

`backend/`: Python 3.13, FastAPI, uvicorn, pydantic-settings, nothing else at runtime. Three layers and a settings
module: `app/api` (routers), `app/core` (pure logic and domain errors), `app/adapters` (one module per outside
service plus its fake, injected with `Depends`), `app/settings.py` (the only env reader). `app/main.py` has
`create_app()` and the one table that maps domain errors to HTTP statuses. `backend/check.sh` runs ruff, pyright,
pytest and `uv audit`, and CI calls it. Rules and layout: [docs/ENGINEERING.md](../ENGINEERING.md) §1 and §3.

## Alternatives considered

- None considered: owner's call.

## Consequences

- Teammates code against FastAPI routers and pydantic models; the API contract can be generated as OpenAPI.
- Deliberately out (ENGINEERING.md §1): repositories, a DI container, base classes, per-entity services, DTO
  layers, needless `async`, Docker, a database, auth, CORS, logging frameworks. Each needs its own record to come in.
- Revisit if the chosen challenge needs something a Python web backend can't serve.
