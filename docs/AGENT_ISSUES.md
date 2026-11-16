# Agent Guidelines — Spec Issues

Follow these rules whenever creating or updating GitHub issues.

## Labels & Metadata
- Every spec issue MUST carry the `spec` label plus type labels (e.g., `enhancement`, `wizard`, `ux`).
- After creating an issue, verify labels via `gh issue view <n> --json labels` and fix if needed.

## Definition of Ready (DoR)
- A spec MUST meet the [Definition of Ready](DEFINITION_OF_READY.md) before implementation starts.
- Use the issue form `task_specification.yml`. When creating via CLI (`gh issue create`), include the exact checklist under `## Definition of Ready` and tick only true items.
- A spec must be reviewed by someone other than its author (or independent reviewers) with findings incorporated before counting as ready.
- **Stop rule:** Do not implement a spec whose DoR is unmet or whose prerequisites are unmerged. Comment on the issue instead of guessing or re-implementing prerequisites.

## Scope & Acceptance Criteria
- Separate backend and frontend descriptions and matching acceptance criteria.
- Frontend parts state functional requirements only; visual design comes from the designer.
- Acceptance criteria and the "Definition of Done" field MUST make the [Definition of Done](DEFINITION_OF_DONE.md) verifiable (test levels, OpenAPI, i18n, migrations, docs, hardware verification). Mark inapplicable items `n/a` with a reason.
