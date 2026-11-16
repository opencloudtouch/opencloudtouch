# OpenCloudTouch — Agent Instructions

Applies to all agents (local/cloud). Human rules: [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Communication & Token Efficiency
- **Chat language:** German. Be extremely concise. Give direct answers or code without prose intros/outros.
- **Repo language:** English (code, comments, commits, branches, issues, PRs, docs).
- **Minimal context:** Read only files directly relevant to the task. Avoid broad repo scans unless explicitly asked.

## Architecture & Commands
- **Monorepo:** `apps/backend/` (Python 3.11+, FastAPI, async: routes → service → repository/adapter) & `apps/frontend/` (React 19, TS strict, TanStack Query). Infra in `deployment/`, `scripts/`, `.github/`.
- **Contract:** Backend & frontend connect ONLY via `apps/backend/openapi.yaml`. Never cross-import. After contract changes, run `npm run generate:api` in `apps/frontend`.
- **Quality & Security:** TDD, coverage ≥ 80 %, deterministic tests only (no real hardware in CI). Never use `--no-verify`. Trusted LAN without auth ([.github/SECURITY.md](.github/SECURITY.md)); never log secrets/tokens.
- **Docs:** [ARCHITECTURE.md](docs/ARCHITECTURE.md), [CONFIGURATION.md](docs/CONFIGURATION.md), [CONVENTIONAL_COMMITS.md](docs/CONVENTIONAL_COMMITS.md).

## Git & Quality Gates
- **Branches:** `type/description` (`feat/…`, `fix/…`, `docs/…`). Check `git status` before switching.
- **Commits:** Conventional Commits (English, max 100 chars subject, no AI mentions).
- **DoR / DoD:** Follow [DEFINITION_OF_READY.md](docs/DEFINITION_OF_READY.md) and [DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md). Never implement specs without met DoR or unmerged prerequisites.
- **Workflows:**
  - Before creating/editing issues, read [docs/AGENT_ISSUES.md](docs/AGENT_ISSUES.md).
  - Before creating/updating pull requests, read [docs/AGENT_PRS.md](docs/AGENT_PRS.md).
