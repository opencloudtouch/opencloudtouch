# Definition of Done (DoD)

A change is **done** when it is shippable: it meets its acceptance criteria, is tested, documented, reviewed, green in CI and leaves the product in a releasable state. The DoD is checked on every **pull request** and is already agreed on the **Spec issue**, whose acceptance criteria and "Definition of Done" field must make each item below verifiable.

> Related: [Definition of Ready](DEFINITION_OF_READY.md) · [CLAUDE.md](../CLAUDE.md) · [Architecture](ARCHITECTURE.md) · [Contributing](../.github/CONTRIBUTING.md) · [Conventional Commits](CONVENTIONAL_COMMITS.md)

## How and when it is checked

| Where | Who | How |
|---|---|---|
| **Spec issue** (before implementation) | Spec author and reviewer | Every DoD item that applies is reflected in an acceptance criterion or in the issue's "Definition of Done" field (test levels, docs, OpenAPI, i18n, migrations, hardware verification). Items that cannot apply are marked `n/a` with a reason. |
| **Pull request** (open, review, merge) | PR author ticks the PR template; the reviewer verifies each tick against the diff and CI | A PR is merged only when every applicable item is ticked and CI is green. The PR description maps each acceptance criterion of the linked spec to its test or evidence. |

## Checklist

### 1. Acceptance
- [ ] Every acceptance criterion of the linked spec is met; the PR shows where (test name, screenshot, log or note).
- [ ] The PR is linked to its spec/issue (`Closes #…` only when the whole spec is done; otherwise `Part of #…`).
- [ ] The linked spec met the [Definition of Ready](DEFINITION_OF_READY.md); deviations are documented in the PR.
- [ ] Scope matches the spec: no unrelated refactoring, no unrequested features.

### 2. Code quality
- [ ] Follows the architecture in [ARCHITECTURE.md](ARCHITECTURE.md) and the conventions in [Contributing](../.github/CONTRIBUTING.md) (backend and frontend only touch their own module; the OpenAPI contract connects them).
- [ ] Backend: Black, Ruff, mypy (type hints), Bandit clean. Frontend: Prettier, ESLint, `tsc --noEmit` (strict) clean.
- [ ] No debug output, commented-out code, dead code or unresolved `TODO`/`FIXME` left behind.
- [ ] New dependencies are justified and pinned; licences checked.
- [ ] Hooks were not bypassed (`--no-verify` is forbidden).

### 3. Tests
- [ ] Developed test-first; new/changed behaviour is covered by unit tests and, where it crosses components, integration tests; user flows have an E2E test.
- [ ] Bug fixes include a **regression test written before the fix** and a documented root cause.
- [ ] Coverage of new/changed code is **≥ 80 %** (backend and frontend flags).
- [ ] Tests are deterministic; no `real_devices` tests in CI; the feature works in **mock mode**.
- [ ] No regressions: the full existing suite is green.

### 4. Continuous integration
- [ ] All required CI checks are green: tests, lint, security scan, licence check, commit lint, SonarCloud quality gate.
- [ ] The PR title and every commit follow [Conventional Commits](CONVENTIONAL_COMMITS.md); branch name follows `type/description`.

### 5. Contracts and data
- [ ] API changes: `apps/backend/openapi.yaml` updated and frontend types regenerated (`npm run generate:api`) and committed; errors use the standard `ErrorDetail` with a stable `code`.
- [ ] Database changes: tables/migrations created in the reserved range, upgrade from the previous schema tested, no data loss.
- [ ] Configuration: new `OCT_*` variables are documented and have safe defaults.

### 6. UI (if applicable)
- [ ] All new strings exist in **all 10 locales** with identical placeholders; no raw backend text is shown to users.
- [ ] Loading, empty, error and offline states work; keyboard operation and accessible names/live regions are in place.
- [ ] Layout works at phone width; designer mockups were followed if provided.

### 7. Security and privacy
- [ ] Inputs are validated; XML parsed with `defusedxml`; no secrets, tokens or personal data in code, logs, error `detail`, support bundles or test fixtures.
- [ ] The trusted-LAN assumptions of [SECURITY.md](../.github/SECURITY.md) still hold; new network access is intentional and documented.

### 8. Documentation
- [ ] User-facing behaviour is documented in `docs/` (for example `CONFIGURATION.md`, `TROUBLESHOOTING.md`) and the README feature list where relevant.
- [ ] `CHANGELOG.md` has an entry under *Unreleased*.
- [ ] Architecture-relevant decisions are recorded as an ADR in `docs/adr/`.

### 9. Deployment
- [ ] Docker/Compose/Raspberry Pi impact checked: non-root user, health check, multi-arch (amd64, arm64, arm/v7) still work.

### 10. Review and hardware
- [ ] At least one reviewer other than the author has approved after verifying this checklist; all review threads are resolved.
- [ ] Behaviour that depends on real SoundTouch hardware was verified on a device, **or** is listed in the PR as an open verification with a named owner and a follow-up issue.
- [ ] Follow-up work discovered during implementation is filed as separate spec issues.

## After merge
- The spec/issue is closed (or updated with remaining parts) and labels are corrected.
- Release notes pick the change up via Conventional Commits.

## Exceptions

- **Hotfix:** tests may be deferred and the DoR is reduced, but a post-mortem and a follow-up issue for the missing tests are mandatory.
- **Docs-only or dependency-only PRs** skip items 3, 5, 6 and 9 where they cannot apply; mark them `n/a`.
- An item that does not apply is marked `n/a` with a one-line reason, never silently skipped.
