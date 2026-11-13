## Summary

<!-- What changes and why, in 2-4 sentences. -->

## Linked spec / issue

<!-- "Closes #123" only if this PR completes the whole spec, otherwise "Part of #123". Include the spec title. -->

## Definition of Ready (linked spec)

Checked against [docs/DEFINITION_OF_READY.md](../docs/DEFINITION_OF_READY.md):

- [ ] The linked spec carries the label `spec` and met the Definition of Ready (all items ticked or `n/a` with a reason)
- [ ] The spec was not changed in a way that invalidates it after approval, or the change is described here
- [ ] Prerequisites named in the spec are merged
- [ ] Deviations from the spec (and why): <!-- none / describe -->

## Acceptance criteria evidence

<!-- Map every acceptance criterion of the spec to its evidence: test name, screenshot, log or note. -->

| Criterion | Evidence |
|---|---|
| | |

## Definition of Done

Checked against [docs/DEFINITION_OF_DONE.md](../docs/DEFINITION_OF_DONE.md). Mark items that cannot apply as `n/a` and say why.

**Acceptance and scope**
- [ ] Every acceptance criterion is met; scope matches the spec (no unrelated changes)

**Code quality**
- [ ] Lint, format, types and Bandit clean (Black/Ruff/mypy, Prettier/ESLint/`tsc`); no debug output, dead code or open TODOs
- [ ] New dependencies justified, pinned, licence checked; hooks not bypassed

**Tests**
- [ ] Developed test-first; unit/integration/E2E tests added as needed; regression test for bug fixes
- [ ] Coverage of new/changed code ≥ 80 %; tests deterministic; works in mock mode
- [ ] Full existing suite green (no regressions)

**CI and commits**
- [ ] All required CI checks green (tests, lint, security, licences, commit lint, SonarCloud)
- [ ] PR title and commits follow Conventional Commits

**Contracts and data**
- [ ] `openapi.yaml` updated and frontend types regenerated and committed (if the API changed)
- [ ] Migrations in the reserved range and upgrade path tested (if the DB changed)
- [ ] New `OCT_*` variables documented with safe defaults

**UI** (if applicable)
- [ ] Strings in all 10 locales; loading/empty/error/offline states; keyboard and screen-reader support; phone width OK

**Security and privacy**
- [ ] Inputs validated, `defusedxml` for XML, no secrets/tokens/personal data in code, logs, errors or fixtures

**Documentation and deployment**
- [ ] `docs/`, README and `CHANGELOG.md` (*Unreleased*) updated; ADR for architectural decisions
- [ ] Docker/Raspberry Pi impact checked (non-root, health check, multi-arch)

**Review and hardware**
- [ ] A reviewer other than the author verified this checklist; all review threads resolved
- [ ] Hardware-dependent behaviour verified on a device, or listed below as an open verification with an owner

## Open verifications and follow-ups

<!-- Hardware checks still needed (with owner) and follow-up spec issues. "None" if there are none. -->
