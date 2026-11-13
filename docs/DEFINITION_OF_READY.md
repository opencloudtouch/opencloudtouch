# Definition of Ready (DoR)

A work item is **ready** when a developer (or an autonomous agent) can implement it end to end **without asking questions**. The DoR is checked on every **Spec issue** (label `spec`) before implementation starts, and re-verified on every **pull request**: a PR may only start from a spec that met the DoR (or documents the deviation).

> Related: [Definition of Done](DEFINITION_OF_DONE.md) · [CLAUDE.md](../CLAUDE.md) · [Architecture](ARCHITECTURE.md) · [Contributing](../.github/CONTRIBUTING.md)

## How and when it is checked

| Where | Who | How |
|---|---|---|
| **Spec issue** (before implementation) | Author ticks the checklist in the issue form; a **second reviewer** (maintainer or an independent review) confirms | Every item below is ticked or marked `n/a` with a reason. Open points are resolved, not deferred. |
| **Pull request** (at PR open and at review) | PR author and reviewer | The PR template asks: "Linked spec met the DoR?". If the spec was changed after approval or items were missed, say so in the PR and fix the spec first. |

Issues created without the form (for example with `gh issue create`) must contain the same checklist as a `## Definition of Ready` section in the body.

## Checklist

### 1. Problem and value
- [ ] The problem, the affected user and the expected benefit are described (user story or equivalent).
- [ ] The originating issue, discussion or report is linked ("Related issue"); duplicates are checked.
- [ ] Scope is explicit: what is **in** and what is **out of scope**.

### 2. Scope and size
- [ ] The affected modules are named: 🖥️ frontend, ⚙️ backend, 🔗 full-stack, 🤖 GitHub Action, 🚀 deployment.
- [ ] The work fits into reviewable PRs; larger work is split into ordered parts (for example backend PR, then frontend PR).
- [ ] Priority and type labels are set. **Every spec issue carries the label `spec`.**

### 3. Acceptance criteria
- [ ] Criteria are testable (Given/When/Then), numbered and unambiguous.
- [ ] Backend and frontend parts have **separate** descriptions and **separate** criteria that match each other (endpoints, field names, error codes).
- [ ] Error paths, edge cases, limits and defaults are covered (empty, maximum, invalid, offline device, concurrency where relevant).
- [ ] Every requirement in the description is covered by at least one criterion.

### 4. Design and contracts
- [ ] API contract is specified: endpoints, request/response examples, status codes, error `code`s, validation rules.
- [ ] Data model, configuration (`OCT_*` variables) and migrations are specified (reserved migration version range if applicable).
- [ ] Behaviour in **mock mode** and with missing/legacy data is defined.
- [ ] Claims about existing code were verified against the repository (files, functions, endpoints exist).
- [ ] The design follows the architecture described in [ARCHITECTURE.md](ARCHITECTURE.md) (clean architecture: routes → service → repository/adapter; frontend/backend separated by the OpenAPI contract); deviations are justified (ADR needed?).

### 5. UX (if the work has a UI)
- [ ] The frontend part states **functional requirements** (behaviour, data, states, placement by page); visual design comes from the designer and is not blocking.
- [ ] Loading, empty, error and offline states are defined.
- [ ] Accessibility expectations and i18n (all 10 locales) are stated.

### 6. Test strategy
- [ ] Test levels are named (unit, integration, E2E) with the key cases.
- [ ] Anything that cannot be verified without real hardware is listed as an **assumption** with a named verifier; it does not block the Definition of Done.

### 7. Security, privacy and risk
- [ ] Trusted-LAN threat model checked ([SECURITY.md](../.github/SECURITY.md)); input validation, secret handling and logging (no secrets, no full URLs with tokens) are defined.
- [ ] Risks, trade-offs and known limitations are written down.

### 8. Dependencies and readiness
- [ ] Prerequisites and blockers are listed; ordering is stated ("do not start until X is merged").
- [ ] Open questions are resolved. No `TBD`, `TODO` or "decide later" remains.
- [ ] Documentation impact is identified (`docs/`, README, CHANGELOG, OpenAPI).
- [ ] A review of the spec (maintainer or independent reviewers) is done and its findings are incorporated.

## Exceptions

- **Hotfix (P0/P1):** the DoR may be reduced to problem, severity, minimal fix and rollback plan; the full spec is written afterwards.
- **Trivial changes** (typos, dependency bumps by Dependabot, pure documentation fixes) do not need a spec; they still meet the Definition of Done.
- An item that does not apply is marked `n/a` with a one-line reason, never silently skipped.
