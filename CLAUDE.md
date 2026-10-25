# OpenCloudTouch — instructions for Claude Code and other coding agents

These rules apply to every agent working in this repository (local and cloud sessions). Humans contributing here follow the same quality gates; see [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Language (applies to every session)

- **Communication with the user in the chat: German.** This includes answers, questions, status reports and summaries addressed directly to the user.
- **Everything else: English** — code, comments, identifiers, commit messages, branch names, issues, PR titles and descriptions, review comments, repository documentation and file contents.

## Project in one minute

- Monorepo: `apps/backend/` (Python 3.11+, FastAPI, async, clean architecture: routes → service → repository/adapter) and `apps/frontend/` (React 19, TypeScript strict, TanStack Query). Deployment and CI live in `deployment/`, `scripts/`, `.github/`.
- The backend and frontend are connected only by the OpenAPI contract (`apps/backend/openapi.yaml`); after contract changes run `npm run generate:api` in `apps/frontend`. Never import across `apps/backend` and `apps/frontend`.
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Configuration: [docs/CONFIGURATION.md](docs/CONFIGURATION.md). Commits: [docs/CONVENTIONAL_COMMITS.md](docs/CONVENTIONAL_COMMITS.md).
- Test-first development; coverage ≥ 80 %; deterministic tests only (no real-device tests in CI). Never bypass hooks (`--no-verify`).
- Threat model: trusted LAN, no authentication by design ([.github/SECURITY.md](.github/SECURITY.md)). No secrets or full token-bearing URLs in code or logs.

## Definition of Ready and Definition of Done

Two quality gates apply to every contributor. The full criteria live in [docs/DEFINITION_OF_READY.md](docs/DEFINITION_OF_READY.md) and [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md). Do not copy or weaken them.

### Spec issues (label `spec`)

- Every spec issue MUST carry the label `spec` (plus type labels such as `enhancement`, `wizard`, `ux`). After creating an issue, verify the labels (`gh issue view <n> --json labels`) and fix them.
- A spec MUST meet the **Definition of Ready** before implementation starts. The issue form `task_specification.yml` contains the checklist; when creating a spec without the form (for example with `gh issue create`), put the same checklist into the body as a `## Definition of Ready` section and tick only what is true.
- The spec's acceptance criteria and its "Definition of Done" field MUST make the **Definition of Done** verifiable (test levels, OpenAPI, i18n, migrations, docs, hardware verification); items that cannot apply are marked `n/a` with a reason.
- Backend and frontend parts have separate descriptions and separate, matching acceptance criteria. Frontend parts state functional requirements; visual design comes from the designer.
- A spec is reviewed by someone other than its author (or by independent reviewers) and the findings are incorporated before it counts as ready.
- Do not start implementing a spec whose Definition of Ready is not met or whose prerequisites are not merged: stop and comment on the issue instead of guessing or re-implementing a prerequisite.

### Pull requests

- Fill in `.github/pull_request_template.md` completely. It re-checks the **Definition of Ready** of the linked spec and contains the **Definition of Done** checklist. Mark non-applicable items `n/a` with a reason; never delete items.
- Link the spec (`Closes #…` only when the PR completes it, otherwise `Part of #…`) and map every acceptance criterion to its evidence.
- Reviewers (human or agent) verify each ticked item against the diff and CI; an unchecked applicable item blocks the merge.
- Hardware-dependent behaviour that was not verified on a real device is listed under "Open verifications and follow-ups" with an owner.
- Hotfixes may reduce the DoR and defer tests, but need a post-mortem and a follow-up issue.
- Commits, PR titles and descriptions follow Conventional Commits, are English, and contain no references to AI tools or assistants.

## Git workflow

- Branches are named `type/description` (`feat/…`, `fix/…`, `docs/…`); check `git status` before switching branches so uncommitted work is not lost.
