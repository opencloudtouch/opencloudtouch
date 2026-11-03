# Drafts of the five `[Spec]` issues for the OCT status system

Status: drafts for the maintainer review (MA-1). Nothing is published yet. Each draft becomes one GitHub issue with the labels `spec` and `enhancement`, created in this order; the numbers of earlier issues replace the "Depends on" placeholders at creation time.

Common to all five: the design is `docs/superpowers/specs/2026-10-29-oct-status-system-design.md`, the tasks are in `docs/superpowers/plans/2026-10-30-oct-status-system.md`. The work is tooling only (Python scripts, GitHub Actions, repository configuration, documentation): no backend or frontend application code, no OpenAPI, i18n, database migration or mock-mode change; these Definition of Done items are `n/a` in every issue. Hardware verification is `n/a` as well. Acceptance criteria are written as Given/When/Then and each maps to tests of the named plan tasks.

The last Definition of Ready item ("reviewed by someone other than the author") stays unticked until the maintainer confirms the review in a comment.

---

## Issue 1: `[Spec]: Status system foundation - script suites in CI, defect fixes, label taxonomy`

**Work Type:** Infrastructure / DevOps. **Related Issue:** none (design spec above). **Priority:** High. **Complexity:** M (3-5 days).

**Problem & Solution Overview.** The test suites under `scripts/` (`issue_handler`, `pr_reviewer`, `test_e2e_shard_distribution.py`) run in no CI job. Running them found a month-dependent test, a never-matching regex and a wrong thank-you score in the weekly KB scan, `issue_handler` at 76.7 % against its own gate of 80 %, and 8 ruff findings. This issue puts all script suites into one CI job `Scripts Tests`, fixes those defects, creates the new package `scripts/oct_status` (config, model types), adds the label taxonomy with an idempotent sync, and aligns the issue handler and Dependabot with the new labels. Out of scope: the status engine itself (issue 2).

**User Stories.** As a maintainer I want broken script tests to fail a PR so that bot code is not silently rotting. As a maintainer I want one label vocabulary (`phase:*`, `wait:*`, `resolution:*`) so that I can filter by state.

**Acceptance Criteria.**
1. **Given** a PR, **when** CI runs, **then** the job `Scripts Tests` runs ruff and pytest for `issue_handler` (coverage gate 80 %), `pr_reviewer` (gate 57 %), the shard-distribution test and `oct_status` (Python 3.13, and `oct_status` also on 3.11), and `CI Summary` fails if it fails. (Tasks 2a-2e, 1)
2. **Given** a cost file for the current month with cost 0.95 and a budget of 0.90, **when** the suite runs in any month, **then** `test_budget_exceeded` passes. (Task 2a)
3. **Given** the text "how do i pair a speaker" or "why is the volume low", **when** the pattern scan runs, **then** the thread lists a non-empty `patterns`; **given** the body "thanks", **then** the score is 2 and `quality.solved` is 1. (Task 2b)
4. **Given** `ruff check .` in `scripts/issue_handler` and `scripts/pr_reviewer`, **then** it reports no finding. (Task 2d)
5. **Given** the label set of the repository, **when** the sync runs with `dry_run=true`, **then** it lists the 7 renames (`wip`, `needs-info`, `blocked`, `accepted`, `duplicate`, `wontfix`, `invalid`), the labels to create and the recolors of `spec` (`8250df`) and `enhancement` (`b8f0c6`) and writes nothing; **when** it runs with `dry_run=false`, **then** a second run performs no write and `prio:*`, `priority: *`, `review`, `community*` and `gitar-*` are never written. (Tasks 3, 5)
6. **Given** a report that needs more information, **when** the issue handler classifies it, **then** it adds `wait:reporter`; the fallback adds `phase:new` (never `needs-triage`); events whose sender is the bot account are ignored. (Task 4)
7. **Given** `.github/dependabot.yml`, **then** every label it names exists and no `reviewers`/`assignees` entry is the placeholder `user`. (Task 4)

**Implementation Tasks.**
- [ ] Task 1 package skeleton, config, model types
- [ ] Tasks 2a-2e month test, regex and scoring fix, CI-ready legacy suites, ruff, CI job
- [ ] Task 3 label taxonomy and sync
- [ ] Task 4 issue handler and Dependabot alignment (after maintainer action MA-2)
- [ ] Task 5 CLI entry point and workflow, then maintainer action MA-3 (run the label sync)

**API Changes.** None.

**Test Strategy.** Unit tests with `httpx.MockTransport` for the label sync (rename keeps assignments, second run is a no-op, dry run writes nothing, foreign labels untouched); regression tests for the three script defects; consistency tests for the Dependabot labels and the spotlight exclusion list; `actionlint` for the workflow. Edge cases: label already renamed, label missing, rate limit retry.

**Affected Components.** `scripts/oct_status/` (new), `scripts/issue_handler/` (tests, `pipeline.py`, `heuristic.py`, `action.py`, `rules.yml`, `pyproject.toml`, `requirements-dev.txt`, `knowledge_base/*`), `scripts/pr_reviewer/` (`pyproject.toml`, `requirements-dev.txt`, tests), `.github/workflows/ci.yml`, `.github/workflows/issue-handler.yml`, `.github/workflows/oct-status.yml` (new), `.github/dependabot.yml`.

**Definition of Done.**
- [ ] All tasks completed; all acceptance criteria met
- [ ] Coverage of new/changed code >= 80 %; tests deterministic; full existing suites green
- [ ] Lint (ruff, mypy for `oct_status`) clean; Conventional Commits
- [ ] `docs/` updated where behaviour changes (the weekly KB report change is described in the PR)
- [ ] OpenAPI, i18n, migrations, mock mode, UI, hardware verification: `n/a` (tooling only)
- [ ] Docker/Raspberry Pi impact: `n/a` (no image change)

**Definition of Ready.**
- [x] Problem, user story and originating issue/discussion are described; scope and out of scope are explicit
- [x] Affected modules are named and the work is split into reviewable PRs where needed; the label `spec` is set
- [x] Acceptance criteria are testable (Given/When/Then), cover error paths and edge cases, and backend and frontend have separate, matching criteria (`n/a`: no application code)
- [x] API contract, data model, configuration, mock-mode behaviour and claims about existing code are specified and verified (`n/a` except the verified claims about the script suites)
- [x] Frontend part states functional requirements only (`n/a`: no UI)
- [x] Test strategy is defined; hardware-dependent items are listed as assumptions with a named verifier (`n/a`)
- [x] Security, privacy and risks are considered (trusted-LAN model, no secrets in logs)
- [x] Dependencies and ordering are stated; no open questions or TBD remain; documentation impact is identified
- [ ] The spec was reviewed by someone other than the author (or independent reviewers) and the findings are incorporated

**Dependencies & Blockers.** None. Needs the maintainer actions MA-2 (before Task 4) and MA-3 (after merge).

**Risks & Considerations.** The label sync renames labels repository-wide (dry run first, rename keeps assignments). The `how/why` and thank-you fixes change the weekly `kb-growth` report. Between merge and sync the issue handler may create `wait:reporter` with a default color; the sync recolors it.

---

## Issue 2: `[Spec]: Status system engine in shadow mode`

**Work Type:** Infrastructure / DevOps. **Related Issue:** issue 1 (Depends on). **Priority:** High. **Complexity:** L (1-2 weeks).

**Problem & Solution Overview.** Artifacts show no state and no connected artifacts; the stack #560 > #570 > #571 > #572 > #573 > #574 is only visible by opening seven PRs. This issue builds the engine: relation graph, snapshot facts, the pure rules engine (`derive`), the status block and guide comment renderers, an idempotent applier and the event pipeline with the workflow in shadow mode (computes everything, writes only to the job summary). Out of scope: writing to artifacts, commands, escalation (issue 3).

**User Stories.** As a maintainer I want every artifact to show its phase, what it waits for and its related artifacts, so that I see blockers without opening a chain of PRs.

**Acceptance Criteria.**
1. **Given** the recorded fixture of PR #574, **when** the block is rendered, **then** it shows phase `draft`, wait `prerequisite`, the chain `main > #560 > #570 > #571 > #572 > #573 > #574`, the root blocker #560 and the relations table. (Tasks 6-9)
2. **Given** a ready PR by a maintainer, **when** there is no `oct-support` approval on the head, **then** `wait:maintainer` is set; **given** an approval on an older sha, then again; **given** an approval by `gitar-bot[bot]`, then it does not count; **given** a push by `formatter-bot` after the approval, then the approval stands; **given** a push by `gitar-bot[bot]`, then it is invalidated. (Task 8)
3. **Given** unresolved review threads, a `CHANGES_REQUESTED` review by `gitar-bot[bot]` or a failed Sonar gate, **then** `wait:findings` is set; **given** skipped or absent checks, **then** `wait:ci` ignores them. (Task 8)
4. **Given** a body with CRLF line endings and 64,900 characters, **when** the block is spliced in, **then** line endings are kept and the table is truncated below 65,536 characters. (Task 9)
5. **Given** a Dependabot PR, **when** its body is regenerated, **then** the block lives in the pinned comment and the body is not written. (Task 10)
6. **Given** an unchanged artifact, **when** the applier runs a second time, **then** it performs zero writes. (Task 10)
7. **Given** any supported event, **when** the pipeline runs with `--dry-run`, **then** nothing is written and the job summary contains block and planned writes; **given** a change in a 40-node stack, **then** at most 25 nodes are recomputed; **given** `--audit`, **then** drift on all open artifacts is found. (Task 11)

**Implementation Tasks.**
- [ ] Task 6 relation graph and sanitized fixtures
- [ ] Task 7 snapshot facts and kind detection
- [ ] Task 8 rules engine
- [ ] Task 9 block renderer and guide comment
- [ ] Task 10 idempotent applier
- [ ] Task 11 event pipeline and shadow workflow; maintainer action MA-4 (Gitar dashboard); one shadow week; maintainer action MA-5 (go/no-go)

**API Changes.** None (GitHub REST only).

**Test Strategy.** Table-driven tests for every rule of the derivation table; golden tests for block and guide of #537, #560, #573, #574, #575, #577 and a Dependabot PR; applier tests with a recording mock transport (idempotence, owned namespaces, pinned comment, duplicate cleanup); sanitized fixtures contain no IPs, e-mail addresses or tokens. Edge cases: CRLF, size limit, unresolved references, announcements without block.

**Affected Components.** `scripts/oct_status/` (graph, facts, rules, render, guide, apply, main, tests), `.github/workflows/oct-status.yml`.

**Definition of Done.** All tasks completed; all acceptance criteria met; coverage >= 80 %; lint clean; docs: handbook comes with issue 4; shadow-week comparison recorded in the PR; OpenAPI, i18n, migrations, mock mode, UI, hardware: `n/a`.

**Definition of Ready.** Same eight items as issue 1 ticked (`n/a` for UI, API and hardware items, with the reasons above); last item (independent review) unticked.

**Dependencies & Blockers.** Depends on issue 1 being merged. The workflow runs in shadow mode only; it must not write to artifacts.

**Risks & Considerations.** Secondary rate limits; event loops from the bot's own writes (idempotence is a criterion); Dependabot regenerating bodies; Gitar "Enhance summaries" (checked in MA-4).

---

## Issue 3: `[Spec]: Status system write mode, commands and escalation`

**Work Type:** Infrastructure / DevOps. **Related Issue:** issue 2 (Depends on). **Priority:** High. **Complexity:** L.

**Problem & Solution Overview.** After a clean shadow week the engine writes: labels, block and guide comment converge on every event; maintainers and authors steer through `/oct` commands; manual rule breaks are answered with an escalating notice (hint, hint with override, block). Automation pushes to protected paths (Gitar) are flagged. Existing artifacts are backfilled without comments or strikes. Out of scope: hooks, handbook, required check (issues 4, 5).

**User Stories.** As a maintainer I want `/oct approve`, `/oct ready` and friends so that state changes are explicit and validated. As a contributor I want a clear notice with the next steps when I break a rule.

**Acceptance Criteria.**
1. **Given** `/oct ready --reviewer <login>` by the spec author, **then** it is rejected unless the reviewer is `independent-review` or another person, and rejected with the list of open DoR items when the checklist is incomplete. (Task 12)
2. **Given** `/oct approve`, **then** one review request for `oct-support` is made, re-requested if it already reviewed an older head. (Task 12)
3. **Given** `/oct override <reason>` by a user without `maintain`/`admin`, **then** it is rejected; by a maintainer it is accepted and logged in the ledger. (Task 12)
4. **Given** the same (artifact, rule) pair twice within 60 days, **then** the user's level is 1; a second pair gives 2; 61 days later 0; overridden violations and violations of automation actors or first-time fork authors do not count; before the configured activation date no strikes apply. (Task 13)
5. **Given** level 3, **then** the check `oct-status` fails for a PR, and on an issue the hand-set fact label is removed again and noted in the guide comment. (Tasks 13, 14)
6. **Given** a push by `gitar-bot[bot]` touching `.github/workflows/**`, **then** `wait:findings` is set and the files are named, until a maintainer runs `/oct accept-paths`; the same push by a human changes nothing. (Task 14)
7. **Given** a backfill that hits a rate limit on the 5th artifact, **then** it stops cleanly and the next run resumes without repeating the first four; it creates no guide comments and no strikes. (Task 14)

**Implementation Tasks.**
- [ ] Task 12 commands
- [ ] Task 13 ledger, violation detectors V01-V08, ladder
- [ ] Task 14 protected paths, write mode, backfill; maintainer action MA-6 (run the backfill)

**API Changes.** None.

**Test Strategy.** Command parsing and authorization tests; ledger tests with an injected clock; one test per rule V01-V08 plus a non-triggering variant; backfill tests with a mock transport and injected sleep; `actionlint`.

**Affected Components.** `scripts/oct_status/` (commands, ledger, violations, rules, main, guide, backfill), `.github/workflows/oct-status.yml`.

**Definition of Done.** All tasks completed; acceptance criteria met; coverage >= 80 %; lint clean; backfill counts and spot check recorded in the PR; docs with issue 4; OpenAPI, i18n, migrations, mock mode, UI, hardware: `n/a`.

**Definition of Ready.** As issue 2 (independent review unticked).

**Dependencies & Blockers.** Depends on issue 2 being merged and on the maintainer's go after the shadow week (MA-5).

**Risks & Considerations.** The workflow starts writing to about 220 artifacts; a wrong derivation would show immediately (mitigated by the shadow week and by backfill in batches). Notices must never start with `gitar` or mention `@gitar-bot`.

---

## Issue 4: `[Spec]: Status system hooks, Gitar rules and handbook`

**Work Type:** Infrastructure / DevOps. **Related Issue:** issue 3 (Depends on). **Priority:** Medium. **Complexity:** M-L.

**Problem & Solution Overview.** Agents and subagents can drop the status block, forge fact labels or open PRs against unready specs. This issue adds committed `.claude` hooks (body splice, label guard, PR creation gate, Bash routing, session context), Gitar rule files, a short section in `CLAUDE.md`, and `docs/WORKFLOW.md` with golden-tested examples (#537 > #573/#574 stack, bug #575, a Dependabot PR). It also verifies, on a throwaway PR, how Gitar commits, `formatter-bot` and the `Approve Check` interact. Out of scope: required check (issue 5).

**User Stories.** As a maintainer I want agents stopped before they break the workflow, and a handbook so that new maintainers understand it.

**Acceptance Criteria.**
1. **Given** a hook probe in a local session, **then** the result states whether `updatedInput` is honoured and whether hooks fire for subagents; if not, the design is corrected before the hooks are built. (Task 15, MA-7)
2. **Given** a write with a `body` by a hooked session, **then** the current block is spliced in; if the block cannot be read, the write is denied and points to a comment. (Task 16)
3. **Given** a PR creation without `Closes #n`/`Part of #n`/`/oct no-spec`, with deleted template items, or against a spec below `ready` (unless stacked on its prerequisite), **then** it is denied with the valid next steps from the guide comment. (Task 16)
4. **Given** `gh issue edit`, `gh pr edit` or a direct API write through Bash, **then** it is denied with the allowed route. (Task 16)
5. **Given** the Gitar and Claude files, **then** they name the block, the three label namespaces, Conventional Commits and the apply restrictions, and `CLAUDE.md` links the handbook. (Task 17)
6. **Given** every marked snippet in `docs/WORKFLOW.md`, **then** it equals the renderer output for its fixture, every rule V01-V08 has an anchor and every command is documented. (Task 18)
7. **Given** the throwaway-PR experiment, **then** the commit author and message of a Gitar fix, the re-approval behaviour of `Approve Check` and the Gitar/`formatter-bot` interaction are recorded in the design spec; if `Approve Check` re-approves without a new review, `check_and_approve` is changed with a test. (Task 19, MA-8)

**Implementation Tasks.**
- [ ] Task 15 hook feasibility spike (MA-7)
- [ ] Task 16 guard and session hooks
- [ ] Task 17 Gitar and Claude instructions
- [ ] Task 18 handbook and doc snippet tests
- [ ] Task 19 Gitar, `formatter-bot` and approval verification (MA-8)

**API Changes.** None.

**Test Strategy.** Pure-function tests of the hook decision logic with PreToolUse JSON fixtures; golden tests for documentation snippets; repository-file tests; the experiments are documented, not automated.

**Affected Components.** `scripts/oct_status/hooks/`, `.claude/settings.json`, `.gitar/`, `CLAUDE.md`, `docs/WORKFLOW.md`, `.github/CONTRIBUTING.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/task_specification.yml`, `scripts/pr_reviewer/` (conditional).

**Definition of Done.** All tasks completed; acceptance criteria met; coverage >= 80 %; handbook merged with golden tests; verification results in the design spec; OpenAPI, i18n, migrations, mock mode, UI, hardware: `n/a`.

**Definition of Ready.** As issue 2 (independent review unticked).

**Dependencies & Blockers.** Depends on issue 3. Needs the maintainer actions MA-7 and MA-8.

**Risks & Considerations.** Hooks fail closed on body writes (a hook outage blocks agent writes, by design); Gitar reads `.claude/` and `CLAUDE.md` once tracked; the experiment creates and deletes a throwaway PR.

---

## Issue 5: `[Spec]: Status system enforcement - activate strikes and the required check`

**Work Type:** Infrastructure / DevOps. **Related Issue:** issue 4 (Depends on). **Priority:** Medium. **Complexity:** S.

**Problem & Solution Overview.** Until now the system informs. This issue activates the escalation ladder from a configured date, makes `oct-status` a required check on `main` and records two decisions: whether `oct-status` is also red while a `wait:*` label is set, and whether admins may bypass the check (`enforce_admins`). Out of scope: any new rule.

**User Stories.** As a maintainer I want no PR to merge while the state is inconsistent.

**Acceptance Criteria.**
1. **Given** `config.yml`, **then** `strikes_enabled_from` is a date that is not in the future, and strikes count from that date. (Task 20)
2. **Given** the branch protection of `main`, **when** the maintainer has added the context `oct-status`, **then** the API response lists `Mojibake Check` and `oct-status` and a PR shows `oct-status` as Required. (Task 20, MA-9)
3. **Given** the two decisions, **then** they are recorded in `docs/WORKFLOW.md`. (Task 20)

**Implementation Tasks.**
- [ ] Task 20 activation date, decisions, required check (MA-9)

**API Changes.** None.

**Test Strategy.** A config test for the activation date; the branch protection change is verified through the API response and a PR check list.

**Affected Components.** `scripts/oct_status/config.yml`, `docs/WORKFLOW.md`, repository branch protection (maintainer action).

**Definition of Done.** Task completed; criteria met; decisions documented; everything else `n/a` (tooling and repository settings only).

**Definition of Ready.** As issue 2 (independent review unticked).

**Dependencies & Blockers.** Depends on issue 4 being merged and on the maintainer decisions (gate mode, `enforce_admins`).

**Risks & Considerations.** From activation, manual rule breaks block PRs on the third strike; the override command is the release valve. With `enforce_admins` off, an admin merge still bypasses the check.
