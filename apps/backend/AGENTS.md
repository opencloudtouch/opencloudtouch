# Backend Agent Rules (`apps/backend/`)

## Architecture & Conventions

- **Stack:** Python 3.11+, FastAPI, strict `async/await`, mandatory type hints.
- **Layers:** Strict `routes → service → repository/adapter`. Never import from `apps/frontend/`.
- **New modules:** `[domain]/{__init__,service,repository,adapter}.py` + `api/routes.py` (register in `main.py`).
- **Contract:** Any API change requires updating `apps/backend/openapi.yaml`.

## Ponytail Review/Audit Focus

- **XML & Network:** Always use `defusedxml` for device XML parsing; set explicit timeouts on all async HTTP calls.
- **No over-engineering:** Keep services and adapters thin; avoid unnecessary base classes or DI frameworks.

## Verification Commands

- **Unit tests:** `cd apps/backend && python -m pytest tests/unit/ -x -q` (pytest 9, respx, pytest-asyncio; ≥ 80% coverage)
- **Lint & Format:** `cd apps/backend && ruff check src/` (Black + Ruff)
- **Types & Security:** `cd apps/backend && mypy src/opencloudtouch/` and Bandit
