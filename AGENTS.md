# OpenCloudTouch — Agent Instructions

## Communication & Token Efficiency

- **Chat language:** German. Be extremely concise; give direct answers/code without prose intros/outros.
- **Repo language:** English (code, comments, commits, branches, issues, PRs, docs).
- **Minimal context:** Read only files directly relevant to the task. Avoid broad repo scans.

## Monorepo Boundaries & Contract

- **Scopes:** `apps/backend/` (Python 3.11+ FastAPI), `apps/frontend/` (React 19 TS), infra (`deployment/`, `scripts/`, `.github/`). Read local `AGENTS.md` in `apps/backend/` or `apps/frontend/` when working there. For infra/CI tasks, read `docs/AGENT_DEVOPS.md`.
- **Contract:** Backend and frontend communicate ONLY via `apps/backend/openapi.yaml`. Never cross-import. After `openapi.yaml` changes, run `npm run generate:api` in `apps/frontend` and verify with `npm run test:all`.
- **Shared files:** Coordinate changes to `package.json`, `.specify/`, `docs/DEFINITION_OF_*.md`, and `.github/` templates.

## Ponytail & Code Quality Standards

- **Lean code (YAGNI):** Write minimal, direct code. No speculative abstractions, generic wrappers for single use cases, or dead code.
- **Prefer stdlib/native:** Use native Python/TS APIs over extra dependencies.
- **Security & Reliability:** Trusted LAN without auth (`.github/SECURITY.md`). Never log secrets/tokens. Validate external inputs (e.g., `defusedxml` for XML).
- **Testing:** TDD, deterministic tests only (no real hardware in CI), coverage ≥ 80% enforced. Never use `--no-verify`.

## Git & Workflow Gates

- **Branches & Commits:** `type/description` (`feat/…`, `fix/…`). Conventional Commits (English, max 100 chars subject, zero AI tool mentions).
- **DoR / DoD:** Enforce `docs/DEFINITION_OF_READY.md` and `docs/DEFINITION_OF_DONE.md`. Stop and comment if prerequisites are unmerged or DoR is unmet.
- **Lazy-load workflows:** Read `docs/AGENT_ISSUES.md` before creating/editing issues. Read `docs/AGENT_PRS.md` before creating/updating PRs.
