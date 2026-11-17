# OpenCloudTouch — Agent Instructions

## Monorepo Boundaries & Contract

- **Scopes:** `apps/backend/` (Python 3.11+ FastAPI), `apps/frontend/` (React 19 TS), infra (`deployment/`, `scripts/`, `.github/`). Read local `AGENTS.md` in `apps/backend/` or `apps/frontend/` when working there. For infra/CI tasks, read `docs/AGENT_DEVOPS.md`.
- **Contract:** Backend and frontend communicate ONLY via `apps/backend/openapi.yaml`. Never cross-import. After `openapi.yaml` changes, run `npm run generate:api` in `apps/frontend` and verify with `npm run test:all`.
- **Shared files:** Coordinate changes to `package.json`, `.specify/`, `docs/DEFINITION_OF_*.md`, and `.github/` templates.

## Ponytail & Code Quality Standards

- **Lean code (YAGNI):** Write minimal, direct code. No speculative abstractions, generic wrappers for single use cases, or dead code.
- **Prefer stdlib/native:** Use native Python/TS APIs over extra dependencies.
- **Security & Reliability:** Trusted LAN without auth (`.github/SECURITY.md`). Never log secrets/tokens. Validate external inputs (e.g., `defusedxml` for XML).
- **Testing:** TDD, deterministic tests only (no real hardware in CI), coverage ≥ 80% enforced. Never use `--no-verify`.

## Git, Findings & Workflow Gates

- **Branches & Commits:** `type/description` (`feat/…`, `fix/…`). Conventional Commits (English, max 100 chars subject, zero AI tool mentions).
- **Findings workflow (no ticket/branch/PR flood):** Fix findings encountered during testing or development (bugs, wording, layout, minor issues) **directly** as small, individual commits on the findings branch at the end of the stack (the commit body must name the stack branch to which the change belongs). Create **no** new ticket, **no** new branch, and **no** new PR per finding (including for delegated agent tasks). Do not ask whether to create a ticket.
- **DoR / DoD:** Enforce `docs/DEFINITION_OF_READY.md` and `docs/DEFINITION_OF_DONE.md`. Stop and comment if prerequisites are unmerged or DoR is unmet.
- **Lazy-load workflows:** Read `docs/AGENT_ISSUES.md` before creating/editing issues. Read `docs/AGENT_PRS.md` before creating/updating PRs.
