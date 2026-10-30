# OCT Status System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every issue, pull request and discussion shows its lifecycle state, what it waits for and its related artifacts, kept correct by a bot, guarded for agents by hooks and explained by one recycled guide comment.

**Architecture:** A pure rules engine (`derive`) turns a GitHub snapshot into phase, waits and resolution. A renderer writes the status block and the guide comment, an applier makes labels, block and comment converge idempotently. One workflow runs it per event (shadow mode first), `.claude` hooks stop agents before they break the rules, and a ledger drives the escalation ladder for humans.

**Tech Stack:** Python 3.11+ (`httpx`, `PyYAML`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`), GitHub Actions, Claude Code hooks, GitHub REST (GraphQL only inside Actions).

**Spec:** `docs/superpowers/specs/2026-10-29-oct-status-system-design.md` (the plan argues from it; read both).

## Global Constraints

- Code, comments, commits, branch names, issues, PRs and docs are English; chat with the maintainer is German. Commits are Conventional Commits and contain no references to AI tools or assistants and no attribution trailers (`CLAUDE.md`). Never `--no-verify`.
- Test-first, coverage >= 80 % (`fail_under = 80`), deterministic tests only: `httpx.MockTransport`, frozen fixtures, injected clock. No real GitHub or device in CI.
- Python 3.11 compatible (CI lint is pinned to 3.11); ruff line length 120; workflows use `actions/*@v7`-style pins already in the repo.
- Label namespaces owned by the bot: `phase:`, `wait:`, `resolution:`. Foreign labels (`gitar-*`, `dependencies`, `kb-scanned`, `prio:*`, `priority: *`, `community*`, `review`) are never touched.
- Markers verbatim: `<!-- oct-status:v1 hash=<12 hex> -->` ... `<!-- /oct-status -->`, `<!-- oct-next:v1 -->`, `<!-- oct-next-data {...} -->`, `<!-- oct-src:1 -->`.
- Numbers: strike window 60 days; fan-out cap 25 nodes; at most 5 next steps; relations table capped at 25 rows; one guide comment per artifact, never a second one; one ledger issue.
- `pull_request_target` workflows never check out PR code. Writes use `BOT_PAT`, reads `GITHUB_TOKEN`. No tokens, full token-bearing URLs or personal data (IPs, e-mail addresses) in code, logs or fixtures.
- Hooks read through REST only (no GraphQL, no `gh`) and fail closed on body writes.
- No comment written by the bot starts with `gitar` or `@gitar` or mentions `@gitar-bot`.
- Existing script suites (`scripts/issue_handler`, `scripts/pr_reviewer`, `scripts/test_e2e_shard_distribution.py`) run in the same CI job as the new package; they run on Python 3.13 (what the workflows use), `oct_status` additionally on 3.11 (hook floor).
- **Maintainer actions:** whenever a step says MAINTAINER ACTION MA-n, stop, tell the maintainer in German exactly what to do and why (use the block of that id in the section "Maintainer actions"), wait for the reported result and record it in the PR description under "Open verifications and follow-ups".
- Each milestone below is one spec issue (label `spec`, Definition of Ready met) and one PR with the filled `.github/pull_request_template.md`. Do not start a milestone whose spec issue is not ready or whose predecessor is not merged.

## Review Focus

Inputs the spec implies but its acceptance behaviour does not spell out; each has a test in the named task.

1. Bodies edited in the web UI arrive with CRLF line endings and may already be near the 65,536-character limit: splicing the block must keep line endings and truncate the table instead of failing (Task 9).
2. The bot's own label, body and comment writes fire new events: a second run on an unchanged artifact must perform zero writes, otherwise the workflow loops (Task 10).
3. Backfill of ~220 artifacts hits secondary rate limits: it must resume after an interruption without duplicating work and must not create guide comments (notifications) (Task 14).
4. Dependabot regenerates its PR body on rebase: its block must live in the pinned comment and survive a regenerated body (Task 10).
5. `Approve Check` (`pr-review.yml`, on `synchronize`) approves again once all `oct-support` threads are resolved and CI is green, so a Gitar push can be approved without a fresh review of the new code (Task 19).

---

## File Structure

```
scripts/oct_status/                  new package, run as `python -m oct_status` with PYTHONPATH=scripts
  pyproject.toml  requirements.txt  requirements-dev.txt
  config.yml        actor allowlist, gate checks, protected paths, caps
  labels.yml        label taxonomy: name, color, description, rename_from
  config.py         load_config
  model.py          enums, Edge, Snapshot, Derived
  api.py            GitHubApi (httpx, retry, REST + GraphQL)
  facts.py          fetch_snapshot
  graph.py          edges, prose parser, component walk
  rules.py          detect_kind, derive, legal_transitions
  render.py         status block render/extract/splice/hash
  guide.py          next_steps, render_guide, upsert
  apply.py          converge labels, block, guide
  commands.py       /oct parser, authorization, execution
  ledger.py         strike ledger
  violations.py     V01-V08 detectors
  labels_sync.py    idempotent label sync
  backfill.py       rate-limited backfill
  main.py           CLI: --event --audit --check --backfill --labels --dry-run
  hooks/guard.py  hooks/session_start.py
  tools/capture_fixture.py  tools/render_doc_snippets.py
  tests/  (fixtures/ = sanitized JSON of #537 #560 #573 #574 #575 #577 and a Dependabot PR)
.github/workflows/oct-status.yml     new
.github/workflows/ci.yml             modify: job `scripts-tests` ("Scripts Tests"), added to `summary`
scripts/pr_reviewer/pyproject.toml  requirements-dev.txt        new (Task 2c)
scripts/issue_handler/tests/test_pattern_quality_scan.py        new (Task 2b)
.claude/settings.json  .gitar/rules/oct-status.md  .gitar/config/apply.md
docs/WORKFLOW.md                     new
```

---

# Milestone 0 - Foundation, existing suites in CI, labels (spec issue 1)

**Before Task 1:** MAINTAINER ACTION MA-1 (go for the five `[Spec]` issues).

### Task 1: Package skeleton, config and model types

**Files:**
- Create: `scripts/oct_status/{__init__.py,__main__.py,pyproject.toml,requirements.txt,requirements-dev.txt,config.yml,config.py,model.py}`, `scripts/oct_status/tests/{__init__.py,test_config.py,test_model.py}`

**Interfaces:**
- Produces: `Phase`, `Wait`, `Resolution`, `Kind`, `EdgeType` (`StrEnum`); `Phase.label -> str` such as `"phase:in-progress"`; `Actor`, `Config`; `load_config(path: Path) -> Config`; and the plain data types every later task uses, all frozen dataclasses in `model.py`:
  - `Review(user: str, state: str, commit_id: str)`, `Check(name: str, status: str, conclusion: str | None, app: str)`, `Push(sha: str, author: str, paths: tuple[str, ...])`
  - `Edge(type: EdgeType, source: int, target: int, origin: Literal["native","prose"])`
  - `Snapshot(number, is_pr, title, body, state, merged, draft, author, labels: frozenset[str], base_ref, head_ref, head_sha, reviews: tuple[Review, ...], unresolved_threads: int, checks: tuple[Check, ...], closing_refs: tuple[int, ...], sub_issues: tuple[int, ...], blocked_by: tuple[int, ...], pushes: tuple[Push, ...], stack_drift: int | None)`
  - `Derived(phase: Phase, waits: frozenset[Wait], resolution: Resolution | None)`
  - `Graph(edges: list[Edge], snapshots: dict[int, Snapshot], derived: dict[int, Derived])` with `edges_of(number: int, type: EdgeType | None = None) -> list[Edge]`
  - `Actor(login: str, klass: Literal["automation","human"], pushes: bool = False, invalidates_approval: bool = True, block_location: Literal["body","comment"] = "body")`
  - `Config(automation: dict[str, Actor], gate_checks: list[str], protected_paths: list[str], fan_out_cap: int = 25, strike_window_days: int = 60, strikes_enabled_from: date | None = None, maintainer_permissions: tuple[str, ...] = ("maintain", "admin"))`

- [ ] **Step 1: Write the failing tests**
  - `test_load_config_defaults`: `cfg.fan_out_cap == 25`, `cfg.strike_window_days == 60`, `cfg.strikes_enabled_from is None`.
  - `test_actor_profiles`: `automation["formatter-bot"].invalidates_approval is False`; `automation["gitar-bot[bot]"].invalidates_approval is True` and `.pushes is True`; `automation["dependabot[bot]"].block_location == "comment"`; `"oct-support"`, `"github-actions[bot]"`, `"sonarqubecloud[bot]"`, `"github-code-quality[bot]"` present.
  - `test_gates_and_protected_paths`: `"CI Summary" in cfg.gate_checks`; `".github/workflows/**" in cfg.protected_paths`; the other four from the spec (`scripts/oct_status/**`, `.gitar/**`, `.claude/**`, `.gitignore`).
  - `test_snapshot_is_frozen_and_graph_edges_of_filters`: assigning to a `Snapshot` field raises; `edges_of(537, EdgeType.IMPLEMENTED_BY)` returns only that type.
  - `test_enum_labels`: `Phase.IN_PROGRESS.label == "phase:in-progress"`, `Wait.HARDWARE_TEST.label == "wait:hardware-test"`, `Resolution.NOT_REPRODUCIBLE.label == "resolution:not-reproducible"`.
- [ ] **Step 2: Run** `cd scripts/oct_status && python -m pytest -q` - Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** the files above. `pyproject.toml` copies `scripts/issue_handler/pyproject.toml` and adds `pythonpath = [".."]` under `[tool.pytest.ini_options]`. Enum members: phases new, draft, triaged, spec-review, spec-rework, confirmed, ready, in-progress, in-review, verification, done, merged, closed, open, needs-spec, specified, answered; waits and resolutions exactly as in spec section 4.2.
- [ ] **Step 4: Run** the same command - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add package skeleton, config and model types`.

### Task 2a: Fix the month-dependent budget test in issue_handler

**Files:**
- Modify: `scripts/issue_handler/tests/test_cost_tracker.py:27-30` (test `test_budget_exceeded`)

**Why (approved by the maintainer):** the test writes the fixed month `"2026-05"`. `CostTracker` resets a cost file from another month on purpose, so since June 2026 it sees a fresh tracker and fails. The code is right, the test is wrong.

- [ ] **Step 1: Run** `cd scripts/issue_handler && python -m pytest tests/test_cost_tracker.py::TestCostTracker::test_budget_exceeded -q` - Expected: FAIL with `assert False is True`.
- [ ] **Step 2: Change the test** so `month` and `last_updated` come from `datetime.now(timezone.utc)` (`%Y-%m` and `.isoformat()`); cost 0.95 and budget 0.90 stay.
- [ ] **Step 3: Run** the same command, then `python -m pytest -q` - Expected: PASS, whole suite green.
- [ ] **Step 4: Commit** `fix(issue-handler): use the current month in the budget test`.

### Task 2b: Fix the never-matching how/why patterns in the pattern scan

**Files:**
- Modify: `scripts/issue_handler/knowledge_base/pattern_quality_scan.py:21-24` (`PATTERNS`)
- Create: `scripts/issue_handler/tests/test_pattern_quality_scan.py`

**Interfaces:**
- Consumes (existing): `async scan_open_issues(github_client: GitHubClient, kb: KnowledgeBase)`, constants `PATTERNS`, `POSITIVE_FEEDBACK`, `NEGATIVE_FEEDBACK`, `STALE_DAYS = 7`. The function lower-cases title and body, calls `github_client.get_open_issues_since(since)` and writes three YAML files below `.local/agent-work/knowledge-kai/scans/` relative to the working directory (`pattern_quality_threads.yaml`, `..._coverage.yaml`, `..._quality.yaml`).

**Why (approved by the maintainer):** `r"\\bhow\\b"` in a raw string is a literal backslash followed by `bhow`, so `re.search` never matches normal text and questions with how/why are missing from the weekly `kb-growth` report. The fix changes the output of that workflow.

- [ ] **Step 1: Write the failing tests** (same mocking style as `tests/test_kb_growth.py`: `AsyncMock` client, `MagicMock(spec=KnowledgeBase)`; every test uses `monkeypatch.chdir(tmp_path)` and reads the YAML back)
  - `test_patterns_match_how_and_why_questions`: `any(re.search(p, "how do i pair a speaker") for p in PATTERNS)` and the same for `"why is the volume low"`.
  - `test_scan_records_patterns_for_how_question`: an open issue titled "How do I reset my speaker" yields a thread whose `patterns` list is non-empty.
  - `test_stale_after_seven_days`: updated 8 days ago -> `stale is True`; 6 days ago -> `False` (timestamps computed relative to now).
  - `test_feedback_counters`: body "solved" -> `quality.solved == 1`; body "still broken" -> `quality["didn’t_work"] == 1`; stale issue without feedback -> `quality.no_response == 1`.
  - `test_coverage_map_marks_covered_topic`: a KB answer tagged `wizard` and an issue mentioning `wizard` -> `covered_by_kb is True`.
  - `test_thanks_scoring_is_pinned_as_known_issue`: `@pytest.mark.xfail(strict=True, reason="'thanks?' is never in ['thanks','solved','fixed'], so thanks counts as helpful, not solved; follow-up issue")`, expects `quality.solved == 1` for the body "thanks".
- [ ] **Step 2: Run** `cd scripts/issue_handler && python -m pytest tests/test_pattern_quality_scan.py -q` - Expected: the two pattern tests FAIL, the others PASS.
- [ ] **Step 3: Fix** the two entries to `r"\bhow\b"` and `r"\bwhy\b"`. Leave the scoring untouched; the `thanks?` mismatch stays documented by the xfail test and goes to a follow-up issue named in the PR.
- [ ] **Step 4: Run** the same command - Expected: PASS with one xfail.
- [ ] **Step 5: Commit** `fix(issue-handler): match how and why in the KB pattern scan`.

### Task 2c: Make the legacy suites CI-ready (dependencies, coverage gates)

**Files:**
- Modify: `scripts/issue_handler/requirements-dev.txt` (add `pytest-asyncio`), `scripts/issue_handler/pyproject.toml` (`asyncio_default_fixture_loop_scope = "function"`)
- Create: `scripts/pr_reviewer/pyproject.toml`, `scripts/pr_reviewer/requirements-dev.txt` (`-r requirements.txt`, `pytest`, `pytest-asyncio`, `pytest-cov`)
- Test additions only if the gate below fails: `scripts/issue_handler/tests/test_kb_growth.py` (for `run_kb_growth`, `main`)

**Why (approved by the maintainer):** `issue_handler` declares `fail_under = 80` but measures 76.7 % because it never ran in CI; `pr_reviewer` has no gate and its 80 % total counts the test file itself (`main.py` alone is 59 %). The dev requirements lack `pytest-asyncio`, which `asyncio_mode = "auto"` needs.

- [ ] **Step 1: Run** `cd scripts/issue_handler && python -m pytest -q --cov=. --cov-fail-under=80` after Task 2b - Expected: PASS at about 83 % (2b covers most of `pattern_quality_scan.py`). If it prints FAIL, add tests for `kb_growth.run_kb_growth` and `main.run` branches until it passes; no production code changes.
- [ ] **Step 2: Create** the `pr_reviewer` files: pytest config (`testpaths = ["tests"]`, `asyncio_default_fixture_loop_scope = "function"`), `[tool.coverage.run] source = ["."]`, `omit = ["tests/*"]`, `[tool.coverage.report] fail_under = 57`, `show_missing = true`.
- [ ] **Step 3: Run** `cd scripts/pr_reviewer && python -m pytest -q --cov=.` - Expected: PASS at about 59 % (gate 57 keeps it from sinking). Name a follow-up issue in the PR to raise the gate.
- [ ] **Step 4: Run** `cd scripts && python -m pytest -q test_e2e_shard_distribution.py` - Expected: 105 passed.
- [ ] **Step 5: Commit** `test(scripts): make the legacy suites CI-ready`.

### Task 2d: CI job for all script suites

**Files:**
- Modify: `.github/workflows/ci.yml` (new job `scripts-tests`, name `Scripts Tests`, after `frontend-tests`; add it to `summary.needs` and to the fail condition of `summary`)

**Interfaces:**
- Consumes: the package from Task 1, the green legacy suites from Tasks 2a-2c.
- Produces: required-able check named `Scripts Tests`.

- [ ] **Step 1: Write the failing check**: `grep -n "scripts-tests" .github/workflows/ci.yml` must show the job id and its entry in `summary.needs`.
- [ ] **Step 2: Run** the grep - Expected: no match.
- [ ] **Step 3: Implement** the job (`ubuntu-latest`, `actions/setup-python@v7` with `3.13`): install the three `requirements-dev.txt` files in one `pip install`; then one named step per suite - issue_handler (`cd scripts/issue_handler && python -m pytest -q --cov=.`), pr_reviewer (`cd scripts/pr_reviewer && python -m pytest -q --cov=.`), shard distribution (`cd scripts && python -m pytest -q test_e2e_shard_distribution.py`), oct_status (`cd scripts/oct_status && ruff check . && mypy . && python -m pytest -q --cov=.`). The coverage gates come from each `pyproject.toml`. A second `setup-python` with `3.11` then reruns the `oct_status` tests. No legacy lint is added (8 existing ruff findings stay out of scope).
- [ ] **Step 4: Run** `actionlint .github/workflows/ci.yml` and the grep - Expected: clean; one match in the job and one in `summary`.
- [ ] **Step 5: Commit** `ci: run all script test suites`. Optional, see MA-9: add `Scripts Tests` to the required checks.

### Task 3: Label taxonomy and idempotent sync

**Files:**
- Create: `scripts/oct_status/labels.yml`, `scripts/oct_status/api.py`, `scripts/oct_status/labels_sync.py`, `scripts/oct_status/tests/test_labels_sync.py`

**Interfaces:**
- Consumes: `load_config`, enums (Task 1).
- Produces: `GitHubApi(token: str, repo: str, transport: httpx.AsyncBaseTransport | None = None)` with `async request(method: str, path: str, **kw) -> httpx.Response` (retry on 403/429/5xx, base 1 s, factor 2, max 3, jitter) and `async graphql(query: str, variables: dict) -> dict`; `async sync_labels(api: GitHubApi, spec_path: Path, dry_run: bool = False) -> list[str]` returning the performed (or planned) operations; `async ensure_ledger_issue(api: GitHubApi, dry_run: bool = False) -> int`.

- [ ] **Step 1: Write the failing tests** (mock transport with an in-memory label store)
  - `test_renames_legacy_labels`: store has `wip`, `needs-info`, `blocked`, `accepted`, `duplicate`, `wontfix`, `invalid`; after sync these exist as `phase:in-progress`, `wait:reporter`, `wait:prerequisite`, `phase:triaged`, `resolution:duplicate`, `resolution:wontfix`, `resolution:invalid` and the old names are gone (rename is a `PATCH /labels/{old}` with `new_name`, not delete+create).
  - `test_creates_missing_with_colors`: `phase:in-review` -> `2a5cc0`, `phase:verification` -> `1e4590`, `phase:done` -> `1a7f37`, `wait:ci` -> `f2a33a`, `resolution:superseded` -> `c9d1d9`.
  - `test_recolors`: `spec` -> `8250df`, `enhancement` -> `b8f0c6`.
  - `test_leaves_foreign_labels`: `prio:0`, `priority: low`, `review`, `gitar-approved`, `dependencies` are never written.
  - `test_second_run_is_noop` and `test_dry_run_writes_nothing`.
  - `test_ledger_issue_created_once_and_locked`: second call returns the same number; the issue is locked.
- [ ] **Step 2: Run** `python -m pytest tests/test_labels_sync.py -q` - Expected: FAIL.
- [ ] **Step 3: Implement.** `labels.yml` entries `{name, color, description, rename_from?}`. Colors per spec section 9; discussion phases (not pinned by the spec, chosen here): `open` cfe0fa, `needs-spec` a8c5f3, `specified` 5b8ee6, `answered` 1a7f37. The ledger issue is titled `oct-status ledger`, locked, body states that it is machine-written.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add label taxonomy and idempotent label sync`.

### Task 4: Align issue handler and Dependabot with the new labels

**Files:**
- Modify: `scripts/issue_handler/pipeline.py:13` (`CLASSIFICATION_LABELS`), `scripts/issue_handler/stages/heuristic.py:24`, `scripts/issue_handler/stages/action.py:196-212`, `scripts/issue_handler/rules.yml` (labels), `.github/workflows/issue-handler.yml` (`if:`), `.github/dependabot.yml`
- Test: `scripts/issue_handler/tests/test_pipeline.py`, `test_heuristic.py`, `test_action.py`

**Interfaces:**
- Consumes: label names from Task 3.

- [ ] **MAINTAINER ACTION MA-2** (before Step 1): identify the `BOT_PAT` account and its scopes.
- [ ] **Step 1: Write the failing tests**
  - `test_classification_labels_use_new_names`: `{"bug","enhancement","support","wait:reporter"} <= CLASSIFICATION_LABELS`.
  - `test_heuristic_adds_wait_reporter`: the `needs-info` case now calls `add_labels(n, ["wait:reporter"])`.
  - `test_action_uses_phase_new_instead_of_needs_triage`: no call contains `"needs-triage"`; the fallback adds `"phase:new"`.
  - `test_spotlight_exclusions_are_subset_of_actor_config`: every login in `EXCLUDE_LOGINS` of `.github/workflows/monthly-community-spotlight.yml` is a key of `load_config(...).automation` or `scheilch`.
  - `test_dependabot_labels_exist`: every label in `.github/dependabot.yml` is in the set from `labels.yml` plus the repo's current names (`dependencies`, `github_actions`), and no `reviewers`/`assignees` entry equals `"user"`.
- [ ] **Step 2: Run** `cd scripts/issue_handler && python -m pytest -q` and the new dependabot test - Expected: FAIL.
- [ ] **Step 3: Implement** the renames. `issue-handler.yml`: add `&& github.event.sender.login != 'oct-support'` to the job `if:` (the status bot's writes must not re-trigger triage). `dependabot.yml`: keep only existing labels (`dependencies`, `github_actions` for the Actions ecosystem) and drop the placeholder reviewers/assignees. Order note for the PR: merge, then run the label sync once (Task 5); between the two the handler may create `wait:reporter` with a default color, which the sync then recolors.
- [ ] **Step 4: Run** both suites - Expected: PASS.
- [ ] **Step 5: Commit** `fix(issue-handler): use status labels and skip status bot events`.

### Task 5: Sync entry point and first run

**Files:**
- Create: `scripts/oct_status/main.py` (labels part), `.github/workflows/oct-status.yml` (only `workflow_dispatch` with input `mode`), `scripts/oct_status/tests/test_main_labels.py`

**Interfaces:**
- Produces: `main.cli(argv: list[str]) -> int` with `--labels [--dry-run]`; workflow inputs `mode: labels|event|audit|backfill` and `dry_run: boolean` (default true).

- [ ] **Step 1: Write the failing test** `test_cli_labels_dry_run_exits_zero_and_prints_operations` (mock transport, `capsys`).
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement** `cli` reading `GITHUB_TOKEN`/`BOT_PAT` and `GITHUB_REPOSITORY`; workflow `oct-status.yml` with `permissions: {issues: write, pull-requests: write, contents: read}`; `actionlint` clean.
- [ ] **Step 4: Run** the test and `actionlint` - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add CLI entry point and label sync workflow`. After the merge: **MAINTAINER ACTION MA-3** (run the label sync).

**Milestone 0 acceptance:** labels renamed and created, `spec`/`enhancement` recolored, ledger issue exists, all script suites (legacy and new) run green in CI, the two legacy bugs are fixed, no other behaviour change.

---

# Milestone 1 - Engine in shadow mode (spec issue 2)

### Task 6: Sanitized fixtures and graph edges

**Files:**
- Create: `scripts/oct_status/tools/capture_fixture.py`, `scripts/oct_status/graph.py`, `scripts/oct_status/tests/fixtures/*.json`, `scripts/oct_status/tests/test_graph.py`

**Interfaces:**
- Consumes: `Edge`, `EdgeType`, `Graph` (Task 1).
- Produces: `parse_prose_edges(number: int, body: str) -> tuple[list[Edge], list[str]]` (second item = unresolved references); `inverse(edge: Edge) -> Edge`; `walk_component(start: int, neighbors: Callable[[int], Awaitable[list[Edge]]], cap: int) -> set[int]`; `build_graph(snapshots: dict[int, Snapshot]) -> Graph` (native edges from `closing_refs`, `sub_issues`, `blocked_by`, base/head branches; prose edges as fallback).

- [ ] **Step 1: Write the failing tests** (use fixture bodies)
  - `test_part_of_and_closes`: `"Part of #537"` -> `IMPLEMENTS(source=n, target=537)`; `"Closes #531"` the same type.
  - `test_depends_on_prose`: `"Depends on #535"` -> `DEPENDS_ON`; inverse is `BLOCKS`.
  - `test_unresolved_reference_is_listed`: `"see the sleep timer spec"` yields no edge; `"Part of #abc"` lands in the unresolved list.
  - `test_walk_component_respects_cap`: a chain of 40 nodes returns exactly 25.
  - `test_fixtures_are_sanitized`: no fixture contains an IPv4 address, an e-mail address or a token-like string.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement.** `capture_fixture.py` fetches one artifact via REST and writes only titles, labels, states, refs, SHAs, review states, check names and body lines that contain `#<n>` references (no free text). Capture #537, #560, #573, #574, #575, #577 and one Dependabot PR; commit the JSON.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add relation graph and sanitized fixtures`.

### Task 7: Facts and kind detection

**Files:**
- Create: `scripts/oct_status/facts.py`, `scripts/oct_status/tests/test_facts.py`; extend `model.py`, `rules.py` (kind part), `tests/test_kinds.py`

**Interfaces:**
- Consumes: `GitHubApi`, `Config`.
- Consumes: `Snapshot` and friends (Task 1).
- Produces: `async fetch_snapshot(api: GitHubApi, number: int, use_graphql: bool = True) -> Snapshot`; `detect_kind(snap: Snapshot, cfg: Config) -> Kind`.

- [ ] **Step 1: Write the failing tests**
  - `test_fetch_snapshot_pr`: from the #574 fixture: `is_pr`, `draft`, `base_ref == "feat/sleep-timer-backend"`, closing/linked refs contain 537.
  - `test_stack_drift_from_compare`: a PR whose base branch is another PR's head gets `stack_drift == behind_by` from `GET /compare/{base}...{head}`; a PR on `main` gets `None`.
  - `test_threads_use_graphql`: unresolved count comes from the GraphQL response; `use_graphql=False` returns `unresolved_threads == -1` (unknown).
  - `test_detect_kind` parametrized: #537 -> `SPEC`; #575 -> `BUG`; #577 -> `BUG` (support); a title starting `[Tracking]` -> `TRACKING`; `[Test]` -> `TEST_PLAN`; Dependabot PR -> `DEPENDENCY_PR`; PR with title `docs: ...` -> `CHORE_PR`; PR `feat(...)` -> `PULL_REQUEST`; bug issue with `spec` -> `SPEC`; `enhancement` without `spec` -> `FEATURE`.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement** both functions; REST for everything, one GraphQL query for review threads (Actions only).
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): fetch artifact snapshots and detect kinds`.

### Task 8: The rules engine

**Files:**
- Modify: `scripts/oct_status/rules.py`; Create: `tests/test_rules.py`, `tests/test_transitions.py`

**Interfaces:**
- Consumes: `Snapshot`, `Graph` (neighbor snapshots and declared labels), `Config`.
- Produces: `derive(snap: Snapshot, graph: Graph, cfg: Config) -> Derived`; `legal_transitions(kind: Kind, phase: Phase) -> list[str]` (command names such as `"review"`, `"ready"`).

- [ ] **Step 1: Write the failing tests** (table-driven; the spec section 6 table is the oracle)
  - `test_wait_maintainer_for_maintainer_pr`: ready PR by a maintainer, no `oct-support` APPROVED review on head -> `MAINTAINER in waits`; with the approval on head -> not; with the approval on an older sha -> in waits again.
  - `test_other_bots_never_approve`: APPROVED by `gitar-bot[bot]` leaves `MAINTAINER` in waits.
  - `test_foreign_pr_needs_human_write_approval`.
  - `test_formatter_bot_push_keeps_approval_gitar_push_invalidates`: push list with `formatter-bot` after the approval -> approval stands; with `gitar-bot[bot]` -> invalidated.
  - `test_findings`: unresolved thread, `CHANGES_REQUESTED` by `gitar-bot[bot]`, or failed `SonarCloud Code Analysis` each -> `FINDINGS`.
  - `test_ci_ignores_skipped_and_absent_checks`; `test_ci_pending_gate_sets_wait`.
  - `test_prerequisite`: unmerged `stacked-on` parent or open `depends-on` target -> `PREREQUISITE`; merged parent -> not.
  - `test_hardware_test_from_open_test_plan`.
  - `test_phase_for_pr_and_spec`: draft PR -> `DRAFT`; ready PR -> `IN_REVIEW`; spec with open ready PR -> `IN_REVIEW`; all parts merged and hardware wait -> `VERIFICATION`; merged and no wait -> `DONE`.
  - `test_declared_phase_is_kept_and_illegal_one_rejected`: label `phase:ready` with an unticked DoR checklist -> `legal_transitions` excludes it.
  - `test_tracking_phase_from_children`: a `[Tracking]` issue with open sub-issues is `IN_PROGRESS`, with all closed `DONE`.
  - `test_test_plan_closed_clears_target_hardware_wait`: closing the `[Test]` issue removes `HARDWARE_TEST` from the PR/spec it verifies.
  - `test_feature_request_mirrors_spec_and_closes_with_it`: with an open spec the request stays open and shows the spec phase; spec `DONE` -> request `DONE`; spec dropped -> `resolution == SUPERSEDED`.
  - `test_discussion_phases`: `open` -> `needs-spec` (label) -> `specified` (spec edge) / `answered`.
  - `test_mergeable_means_no_wait`: in-review PR with all conditions met has `waits == frozenset()`.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement** `derive` as a pure function in the order of the spec table; no I/O.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add rules engine and state machines`.

### Task 9: Status block renderer and guide comment

**Files:**
- Create: `scripts/oct_status/render.py`, `scripts/oct_status/guide.py`, `tests/test_render.py`, `tests/test_guide.py`, golden files under `tests/fixtures/golden/`

**Interfaces:**
- Consumes: `Snapshot`, `Derived`, `Graph` (with `derived` filled by the caller), `Config`.
- Produces: `render_block(snap: Snapshot, derived: Derived, graph: Graph, cfg: Config) -> str | None` (`None` for announcements); `extract_block(body: str) -> str | None`; `splice_block(body: str, block: str, limit: int = 65_000) -> str`; `block_hash(block: str) -> str` (12 hex); `Step(actor: str, text: str, command: str | None)`; `next_steps(snap, derived, cfg) -> list[Step]` (max 5); `render_guide(snap, derived, steps, notices: list[str], history: list[str]) -> str`.

- [ ] **Step 1: Write the failing tests**
  - `test_golden_block_for_537_573_574_575`: rendered output equals the committed golden (badges, root-blocker line, stack chain for #574 `main > #560 > #570 > #571 > #572 > #573 > #574`, automation row, relations table).
  - `test_render_is_deterministic`: two renders are byte-identical and `block_hash` matches the marker.
  - `test_splice_preserves_crlf` (Review Focus 1): a body with `\r\n` keeps `\r\n` and the block uses it.
  - `test_splice_truncates_table_instead_of_overflowing`: a 64,900-character body plus a 40-row table ends below 65,536 with an "and n more" row.
  - `test_unresolved_refs_listed_not_guessed`.
  - `test_dependency_block_is_light`: a Dependabot PR renders badges and state only, without DoD counter or relations table.
  - `test_chain_marks_parent_moved`: a child with `stack_drift > 0` shows "parent moved" in the chain.
  - `test_announcement_has_no_block`: kind `ANNOUNCEMENT` -> `render_block` returns `None`.
  - `test_next_steps_per_state` parametrized: `wait:maintainer` -> a step with command `/oct approve`; unticked DoR -> a precondition note instead of `/oct ready`; `wait:hardware-test` -> `/oct verified <device>`; never more than 5 steps.
  - `test_guide_sections_and_data_block`: the output contains `<!-- oct-next:v1 -->`, the sections in the order of spec 5a, and a parseable `<!-- oct-next-data {...} -->` JSON with `phase`, `waits`, `next`.
  - `test_guide_never_starts_with_gitar`.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement.** Badges are static Shields.io image URLs with alt text; golden files are produced once by a documented command in the test module docstring and then reviewed by hand.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): render status block and guide comment`.

### Task 10: Idempotent applier

**Files:**
- Create: `scripts/oct_status/apply.py`, `tests/test_apply.py`

**Interfaces:**
- Consumes: `render_*`, `splice_block`, `GitHubApi`.
- Produces: `async apply_state(api: GitHubApi, snap: Snapshot, derived: Derived, block: str | None, guide: str | None, cfg: Config, dry_run: bool = False) -> list[str]` returning the performed write descriptions (empty when nothing changed); `async upsert_guide(api, number, content) -> str`.

- [ ] **Step 1: Write the failing tests** (mock transport recording writes)
  - `test_second_run_makes_zero_writes` (Review Focus 2): apply twice on the same snapshot; the second call returns `[]` and the transport saw no `PATCH`/`POST`/`PUT`/`DELETE`.
  - `test_only_owned_namespaces_change`: foreign labels survive; a manually set fact label is removed again.
  - `test_dependency_pr_uses_pinned_comment` (Review Focus 4): Dependabot PR -> block goes into the guide comment, the body is untouched; after a regenerated body the next apply still writes nothing to the body.
  - `test_guide_upsert_updates_in_place`: marker found -> `PATCH`; no marker -> one `POST`; two marked comments -> the newer is deleted.
  - `test_deleted_guide_is_recreated`.
  - `test_dry_run_writes_nothing_and_reports_plan`.
  - `test_announcement_gets_neither_block_nor_guide`: `block is None and guide is None` -> no writes.
  - `test_bot_edit_event_is_ignored`: an `edited` payload whose sender is the bot returns early (loop guard).
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement** `apply_state` as diff-then-write (labels: compute add/remove sets, body: write only if `block_hash` differs).
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): converge labels, block and guide comment idempotently`.

### Task 11: Event pipeline and shadow-mode workflow

**Files:**
- Modify: `scripts/oct_status/main.py`, `.github/workflows/oct-status.yml`; Create: `tests/test_main_events.py`

**Interfaces:**
- Produces: `async run_event(api: GitHubApi, cfg: Config, event_name: str, payload: dict, dry_run: bool) -> int`; CLI `--event <name> --payload <path> [--dry-run]`, `--audit`, `--check`.

- [ ] **Step 1: Write the failing tests**
  - `test_event_resolves_artifact_number` for `issues`, `pull_request_target`, `pull_request_review`, `issue_comment`, `check_suite` (maps to the PR of the head sha), `discussion`.
  - `test_fan_out_limited_to_component_and_cap`: a change on #560 recomputes #570-#574 only; a 40-node stack processes 25.
  - `test_shadow_mode_writes_only_job_summary`: with `--dry-run` the summary file contains the block and planned writes and the transport saw no write.
  - `test_check_mode_exit_codes`: stale block -> 1; healthy -> 0.
  - `test_audit_heals_drift_on_all_open_artifacts`: three open artifacts, one with a missing block and one with a wrong fact label; `--audit` repairs exactly those two and reports a count of 2.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement.** Workflow triggers: `issues`, `pull_request_target` (opened, edited, synchronize, ready_for_review, converted_to_draft, closed, labeled, unlabeled, review_requested), `pull_request_review`, `pull_request_review_comment`, `issue_comment`, `check_suite: completed`, `discussion`, `discussion_comment`, `schedule` (daily at 03:17 UTC), `workflow_dispatch`. Concurrency `group: oct-status-${{ number }}`, `cancel-in-progress: false`. Job names: `status` (event run) and `oct-status` (check). In this milestone the step runs with `--dry-run`. Checkout only the base ref.
- [ ] **Step 4: Run** the tests and `actionlint` - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add event pipeline and shadow-mode workflow`.
- [ ] **MAINTAINER ACTION MA-4** (after the merge, before the shadow week counts): check the Gitar dashboard settings.

**Milestone 1 acceptance:** the workflow runs on every event in shadow mode and its job summary can be compared with reality for one week. Recorded in the PR: a diff between computed and actual labels for all open artifacts. Before Task 14 starts: **MAINTAINER ACTION MA-5** (go/no-go after the shadow week).

---

# Milestone 2 - Write mode, commands, escalation (spec issue 3)

### Task 12: Commands

**Files:**
- Create: `scripts/oct_status/commands.py`, `tests/test_commands.py`

**Interfaces:**
- Consumes: `legal_transitions`, `GitHubApi`.
- Produces: `Command(name: str, args: str)`; `parse_command(text: str) -> Command | None`; `async authorize(api, login: str, cmd: Command, cfg: Config) -> bool`; `async execute(api, cmd: Command, snap: Snapshot, derived: Derived, actor: str) -> Outcome` where `Outcome(ok: bool, message: str, declare: dict)`.

- [ ] **Step 1: Write the failing tests**
  - `test_parse_all_commands`: every command of spec section 11 parses with its arguments; `"/octopus"` and a command inside a code fence do not parse.
  - `test_ready_requires_complete_dor_and_other_reviewer`: `/oct ready --reviewer scheilch` by the author -> rejected unless reviewer is `independent-review`; unticked `## Definition of Ready` items -> rejected with the list of items.
  - `test_approve_requests_oct_support_review`: one `POST /pulls/{n}/requested_reviewers` with `{"reviewers": ["oct-support"]}`; when `oct-support` already reviewed an older head, the same call re-requests the review.
  - `test_override_needs_maintain_permission_and_is_logged`.
  - `test_unauthorized_command_rejected` (write access missing).
  - `test_no_spec_requires_reason`.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement.** Commands act through labels (declarations) and one REST call each; rejection text goes to the guide comment (Task 9/10), reactions on the command comment (`eyes`, `+1`, `-1`).
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add /oct commands`.

### Task 13: Ledger, violations and the ladder

**Files:**
- Create: `scripts/oct_status/ledger.py`, `scripts/oct_status/violations.py`, `tests/test_ledger.py`, `tests/test_violations.py`

**Interfaces:**
- Produces: `Violation(rule: str, artifact: int, user: str, hint: str)`; `detect(snap, derived, graph, cfg, actor_class: str) -> list[Violation]` (rules `V01`..`V08` of spec section 10); `Ledger(api, issue_number: int, clock: Callable[[], datetime])` with `async record(v: Violation) -> None`, `async level_for(user: str) -> int`, `async record_override(user, artifact, reason) -> None`.

- [ ] **Step 1: Write the failing tests**
  - `test_level_counts_distinct_artifact_rule_pairs_in_60_days`: the same pair twice -> level 1; a second pair -> 2; 61 days later -> back to 0 (injected clock).
  - `test_override_not_counted`.
  - `test_automation_and_first_time_fork_authors_exempt`.
  - `test_detectors`: one test per rule V01..V08 with a minimal snapshot that triggers it and a variant that does not.
  - `test_ladder_messages`: level 1 -> notice without override hint; level 2 -> includes `/oct override`; level >= 3 -> `blocks is True` for PRs and `revert is True` for issues/discussions.
  - `test_no_strikes_before_activation_date`: `cfg.strikes_enabled_from` in the future -> `level_for` is 0 and notices are not escalated.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement.** The ledger stores one JSON comment per event on the ledger issue; reading lists comments with `since` for the window. Notices are rendered into the guide comment's section 5, with the rule anchor `docs/WORKFLOW.md#v01-...`.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add strike ledger and violation detectors`.

### Task 14: Protected paths, write mode and backfill

**Files:**
- Modify: `scripts/oct_status/rules.py`, `main.py`, `.github/workflows/oct-status.yml`; Create: `scripts/oct_status/backfill.py`, `tests/test_protected_paths.py`, `tests/test_backfill.py`

**Interfaces:**
- Produces: `touches_protected(paths: list[str], patterns: list[str]) -> list[str]`; `async backfill(api, cfg, numbers: list[int], state_path: Path, clock, sleep) -> int` (count processed).

- [ ] **Step 1: Write the failing tests**
  - `test_automation_push_to_protected_path_sets_findings_until_accepted`: push by `gitar-bot[bot]` touching `.github/workflows/ci.yml` -> `FINDINGS` and the file named in the notice; label/command `/oct accept-paths` by a maintainer clears it; the same push by a human does nothing.
  - `test_check_fails_for_unaccepted_protected_paths`.
  - `test_backfill_resumes_after_rate_limit` (Review Focus 3): the transport answers 403 with `retry-after` on the 5th artifact; the run stops cleanly, the state file lists 4 done, the second run processes the rest without repeating the first 4.
  - `test_backfill_creates_no_guide_comments_and_no_strikes`.
  - `test_level3_violation_reverts_issue_change_and_fails_pr_check`: a hand-set fact label on an issue at level 3 is removed again and noted in the guide comment; the same violation on a PR makes `--check` exit 1.
  - `test_backfill_sleeps_between_artifacts` (injected `sleep` called, fixed minimum delay).
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement.** Switch the workflow's event run from `--dry-run` to write mode; add `mode=backfill` using `workflow_dispatch` with an integer input `limit` (default 25 artifacts per run) and a printed `remaining:` count. Backfill derives phases from facts only.
- [ ] **Step 4: Run** tests and `actionlint` - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): enable write mode, protected-path guard and backfill`. After the merge: **MAINTAINER ACTION MA-6** (run the backfill in batches).

**Milestone 2 acceptance:** new events converge; open artifacts carry correct labels and blocks; no strikes exist yet (activation date unset).

---

# Milestone 3 - Hooks, Gitar, documentation (spec issue 4)

### Task 15: Hook feasibility spike

**Files:**
- Create: `scripts/oct_status/tools/hook_probe/{settings.json,hook_probe.py}` (removed again in Task 16)

**Interfaces:**
- Produces: recorded answers to two questions, written into spec section 15.

- [ ] **Step 1: Write and commit the probe**: a PreToolUse hook on `Bash` that appends `tool_name` and a session id to `/tmp/hook-probe.log` and returns `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "updatedInput": {"command": "echo rewritten"}}}`.
- [ ] **Step 2: MAINTAINER ACTION MA-7**: run the probe in a local Claude Code session with a prompt that runs `echo original` directly and a second prompt that delegates it to a subagent.
- [ ] **Step 3: Check** the reported output: Expected: the tool output is `rewritten` (updatedInput honoured) and the log has an entry for the subagent call. Write both results into spec section 15.
- [ ] **Step 4: Decide**: if `updatedInput` is not honoured, Task 16 uses deny-with-instruction instead of splicing; if hooks do not fire for subagents, the subagent preamble in `CLAUDE.md` becomes the only prevention and spec section 8 is corrected before Task 16 starts.
- [ ] **Step 5: Commit** `docs: record hook feasibility results in the status system spec`.

### Task 16: Guard and session hooks

**Files:**
- Create: `scripts/oct_status/hooks/{guard.py,session_start.py}`, `.claude/settings.json`, `tests/test_hooks.py`

**Interfaces:**
- Consumes: `extract_block`, `splice_block`, guide data block, rules from Task 13.
- Produces: `decide(tool_name: str, tool_input: dict, current: HookContext) -> Decision` where `HookContext(block: str | None, guide_data: dict | None, spec_phase: Phase | None, has_template: bool)` and `Decision(action: Literal["allow","deny"], reason: str, updated_input: dict | None)`; stdin/stdout JSON wrappers around it.

- [ ] **Step 1: Write the failing tests**
  - `test_body_write_gets_block_spliced`: `issue_write` with a new body -> `allow` with `updated_input.body` containing the current block.
  - `test_body_write_denied_when_block_unreadable` (fail closed), message points to a comment instead.
  - `test_fact_label_write_denied_with_oct_alternative`.
  - `test_pr_creation_gate`: denied when the body has no `Closes #n`/`Part of #n` and no `/oct no-spec`, when template headings are missing or an item was deleted, when the linked spec is below `READY`; allowed when stacked-on its prerequisite.
  - `test_bash_gh_and_api_calls_are_routed`: `gh issue edit`, `gh pr edit`, `curl https://api.github.com/repos/.../issues/..` with `-X PATCH` -> deny with the equivalent allowed route.
  - `test_denial_quotes_next_steps_from_guide_data`.
  - `test_writes_carry_src_marker`: bodies and comments written by a hooked session end with `<!-- oct-src:1 -->`.
  - `test_session_start_injects_block_and_guide_data`.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Implement** `decide` as a pure function; the wrappers fetch context through REST with a 5 s timeout. `.claude/settings.json` registers the hooks (PreToolUse on the GitHub write tools and on `Bash`, SessionStart) and calls `python scripts/oct_status/hooks/...`.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add agent hooks for body, labels and PR creation`.

### Task 17: Gitar and Claude instructions

**Files:**
- Create: `.gitar/rules/oct-status.md`, `.gitar/config/apply.md`; Modify: `CLAUDE.md` (short section), `tests/test_repo_files.py`

- [ ] **Step 1: Write the failing test** `test_gitar_and_claude_files`: `.gitar/rules/oct-status.md` mentions `oct-status` block, `phase:`, `wait:`, `resolution:` and Conventional Commits; `.gitar/config/apply.md` names categories to skip (security-relevant code, `.github/`, `scripts/oct_status/`); `CLAUDE.md` links `docs/WORKFLOW.md`.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Write** the three texts. `apply.md` (natural language, read from the default branch): only unused imports, formatting, typos and documentation findings; skip authentication, SSH and setup wizard code, device protocol code, `.github/`, `.claude/`, `.gitar/` and `scripts/oct_status/`.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `docs: add Gitar rules and workflow pointer`.

### Task 18: Handbook with golden-tested examples

**Files:**
- Create: `docs/WORKFLOW.md`, `scripts/oct_status/tools/render_doc_snippets.py`, `tests/test_docs_snippets.py`, fixtures for the walkthrough steps; Modify: `.github/CONTRIBUTING.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/task_specification.yml` (link lines only)

**Interfaces:**
- Produces: `render_doc_snippets.py` prints every snippet between `<!-- snippet:<name> -->` markers in `docs/WORKFLOW.md`, rendered from fixtures.

- [ ] **Step 1: Write the failing test** `test_docs_snippets_match_renderer`: each marked snippet in `docs/WORKFLOW.md` equals the renderer output for its fixture; `test_every_rule_has_an_anchor`: `V01`..`V08` anchors exist; `test_commands_documented`: every command from `commands.py` appears in the command reference.
- [ ] **Step 2: Run** - Expected: FAIL.
- [ ] **Step 3: Write** `docs/WORKFLOW.md` in the order of spec section 13: lifecycle diagrams (Mermaid), reference tables, command reference, "You are up when...", onboarding checklist, the dated walkthrough (#537 -> #573/#574 with the #560 stack, bug #575, a Dependabot PR) with block, guide comment and labels per step, one anchor per rule with a wrong and a right example, troubleshooting, rollback runbook.
- [ ] **Step 4: Run** - Expected: PASS.
- [ ] **Step 5: Commit** `docs: add the status system handbook`.

### Task 19: Verify Gitar, formatter-bot and the approval flow

**Files:**
- Modify (conditional): `scripts/pr_reviewer/main.py` (`check_and_approve`, `scripts/pr_reviewer/tests/test_main.py`); spec section 15

- [ ] **Step 1: MAINTAINER ACTION MA-8**: run the experiment on a throwaway PR: let `oct-support` approve, push a change via `gitar fix this`, then let `formatter-bot` push. Record: Gitar's commit author and message against "Validate Commit Messages"; whether `Approve Check` re-approves the new head without a new review; whether Gitar stops after the `formatter-bot` push; whether the status block survives Gitar's summary update.
- [ ] **Step 2: Write the failing test** (only if `Approve Check` re-approved without review) `test_approve_requires_new_review_after_automation_push` in `scripts/pr_reviewer/tests/test_main.py`: commits after the last `oct-support` review that are authored by `gitar-bot[bot]` -> `check_and_approve` does not approve.
- [ ] **Step 3: Implement** the minimal change in `check_and_approve`, only if Step 2 was needed.
- [ ] **Step 4: Run** `cd scripts/pr_reviewer && python -m pytest -q` - Expected: PASS.
- [ ] **Step 5: Commit** `fix(pr-review): require a new review after automation pushes` (or `docs: record Gitar verification results` when no code change was needed).

**Milestone 3 acceptance:** hooks block the listed agent actions, Gitar and Claude instructions are in place, the handbook is golden-tested, the verification results are in spec section 15.

---

# Milestone 4 - Enforcement (spec issue 5)

### Task 20: Activate strikes and the required check

**Files:**
- Modify: `scripts/oct_status/config.yml` (`strikes_enabled_from`), `docs/WORKFLOW.md`, spec section 15

- [ ] **Step 1: Write the failing test** `test_config_activation_date_is_set` in `tests/test_config.py`: `load_config(...).strikes_enabled_from` is a `date` that is not in the future.
- [ ] **Step 2: Run** `cd scripts/oct_status && python -m pytest tests/test_config.py -q` - Expected: FAIL (the key is unset since Task 1).
- [ ] **Step 3: MAINTAINER ACTION MA-9** - decide and record: gate mode (strikes and stale blocks only, or also while any `wait:*` is set) and `enforce_admins`. Write both decisions into `docs/WORKFLOW.md`. Set `strikes_enabled_from` to the activation date.
- [ ] **Step 4: Apply as admin** (part of MA-9; UI path in the section "Maintainer actions", or this call):
  ```bash
  curl -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/opencloudtouch/opencloudtouch/branches/main/protection/required_status_checks/contexts \
    -d '["oct-status"]'
  ```
  Expected: the response lists `Mojibake Check` and `oct-status`.
- [ ] **Step 5: Commit** `chore(oct-status): activate strikes and document the merge gate`.

---

## Maintainer actions

The executing agent stops at each marked step, tells the maintainer in German what to do and why (text below), and waits for the result. Nothing here can be done by the agent: it needs repository secrets, repository settings, the Gitar dashboard, a local Claude Code session or a decision.

**MA-1 - Go for the five `[Spec]` issues.** When: before Task 1, and again per milestone. Why: `CLAUDE.md` forbids starting a spec whose Definition of Ready is not met, and the DoR needs a review by someone other than the author; publishing issues is visible to everyone. Do: (1) answer "Ja" to publishing the five issues (the agent creates them from the milestones with labels `spec` and `enhancement` and a `## Definition of Ready` section); (2) open each issue, read the checklist and confirm in a comment that the review is done (name the independent reviewer if it is not you). Report: the five issue numbers confirmed ready.

**MA-2 - Identify the `BOT_PAT` account.** When: before Task 4. Why: the issue handler loop guard, the review requests of `/oct approve` and the ledger writes must use the right login; the repository names `scheilch` in `issue-handler.yml` and `oct-support` in `rules.yml`, and commits on #555 resolve to `oct-support` (spec section 15). Do, on your machine with the secret value in an environment variable (never paste the token anywhere):
```bash
export BOT_PAT=<value of the repository secret BOT_PAT>
curl -sS -D - -o /dev/null -H "Authorization: Bearer $BOT_PAT" https://api.github.com/user | grep -i '^x-oauth-scopes'
curl -sS -H "Authorization: Bearer $BOT_PAT" https://api.github.com/user | python3 -c "import json,sys; print(json.load(sys.stdin)['login'])"
```
Report: the login and the scopes line. Expected: `oct-support`, scopes include `repo` and `write:discussion`. For a fine-grained token the scopes line is empty; then report the permissions shown on the token's settings page (Issues, Pull requests: read/write; Contents: read; Discussions: read/write).

**MA-3 - Run the label sync.** When: after the Milestone 0 PR is merged. Why: it renames the legacy labels (`wip`, `needs-info`, `blocked`, `accepted`, `duplicate`, `wontfix`, `invalid`), creates the new ones and recolors `spec` and `enhancement` for the whole repository, so a dry run comes first. Do: GitHub -> Actions -> "OCT Status" -> Run workflow, branch `main`, `mode` = `labels`, `dry_run` = true; open the run summary and check the operation list (7 renames, the created labels, 2 recolors, nothing on `prio:*`, `priority: *`, `review`, `community*`); then run it again with `dry_run` = false; then open Issues -> Labels and check that `phase:*`, `wait:*`, `resolution:*` exist and the legacy names are gone, and that the issue "oct-status ledger" exists and is locked. Report: ok, or the deviations. Undo: rename labels back in the UI.

**MA-4 - Check the Gitar dashboard.** When: after Task 11 is merged, before the shadow week starts. Why: spec section 15. "Enhance summaries" would rewrite PR descriptions, where the status block lives; "Skip drafts" decides whether the draft stack #570-#574 is reviewed; auto-apply, auto-approve and auto-merge decide whether Gitar pushes, approves or merges. Do: open the Gitar dashboard for the organisation -> Settings -> Configuration (Behavior card and Scope). Report the state of: Auto-apply default, Auto-approve, Auto-merge, Enhance summaries, Skip drafts, Block merges level, Allowed bots. Expected: auto-apply on, auto-approve on, auto-merge off. If Enhance summaries is on, say so; then either switch it off or the plan moves the block into the pinned comment for all PRs.

**MA-5 - Go/no-go after the shadow week.** When: before Task 14. Why: write mode edits labels and bodies of about 220 artifacts; mistakes would only show afterwards. Do: Actions -> "OCT Status", open the runs for #537, #560, #574, #575, #577 and one Dependabot PR plus one `audit` run; in each run summary compare phase, waits and relations with what you see on GitHub. Report: "freigegeben", or the artifact number and what is wrong.

**MA-6 - Run the backfill.** When: right after the Task 14 PR is merged. Why: it sets labels and blocks on the existing artifacts (no comments, no strikes); GitHub rate limits force batches. Do: Actions -> "OCT Status" -> Run workflow, `mode` = `backfill`, `limit` = 25; repeat until the summary prints `remaining: 0`. After the first batch spot-check five artifacts: label set equals the block, no new comment appeared. If a run reports a rate limit, wait the printed time and run again (it resumes). Report: the counts and the spot-check result.

**MA-7 - Hook probe.** When: Task 15. Why: decides whether hooks can splice the block into a body (`updatedInput`) and whether they also fire for subagents; both are claims of spec section 8. Do on a machine with Claude Code, after `git pull` of the branch with the probe:
```bash
rm -rf /tmp/hook-probe && mkdir -p /tmp/hook-probe/.claude && cd /tmp/hook-probe && git init -q
cp <repo>/scripts/oct_status/tools/hook_probe/settings.json .claude/settings.json
cp <repo>/scripts/oct_status/tools/hook_probe/hook_probe.py .
: > /tmp/hook-probe.log
claude -p "Run the bash command: echo original and print its output"
claude -p "Use a subagent to run the bash command: echo original and print its output"
cat /tmp/hook-probe.log
```
Report: the output of the first command (`rewritten` or `original`) and the log lines (is there an entry for the subagent's call?).

**MA-8 - Gitar and approval experiment.** When: Task 19. Why: three open questions of spec section 15: does a Gitar commit pass "Validate Commit Messages", does "Approve Check" re-approve a PR after an automation push without a new review, and does Gitar loop with `formatter-bot`. Do:
```bash
git fetch origin && git checkout -b test/oct-status-probe origin/main
printf 'import os\n' > apps/backend/src/opencloudtouch/_probe.py   # unused import, fails "Lint Code"
git add -A && git commit -m "test: probe oct-status with a failing lint" && git push -u origin test/oct-status-probe
```
Open a ready (not draft) PR titled `test: probe oct-status`, request a review from `oct-support`, resolve its threads until "Approve Check" approves. Let Gitar fix the lint failure (auto-apply is on; if nothing happens within ten minutes comment `gitar fix this`). Then collect: `git log origin/test/oct-status-probe -4 --format='%an <%ae> | %cn | %s'`, whether "Validate Commit Messages" passed on Gitar's commit, whether `oct-support` approved again after Gitar's push and without a new review, whether `formatter-bot` pushed afterwards and what Gitar did, and whether the PR description was changed. Finish by closing the PR and deleting the branch. Report: those four answers.

**MA-9 - Merge gate and required checks.** When: Task 20. Why: it defines what a red `oct-status` means and whether admins can bypass it. Decide: (a) gate mode - red only on strikes and stale blocks, or also while any `wait:*` label is set (the second mode makes `oct-status` the single go/no-go and also holds back native auto-merge); (b) `enforce_admins` on or off. Do: Repository -> Settings -> Branches -> rule for `main` -> Edit -> "Require status checks to pass before merging" -> add `oct-status` (and, if you want it, `Scripts Tests`) -> for (b) tick "Do not allow bypassing the above settings" -> Save. The API call in Task 20 Step 4 is the equivalent. Check: a PR shows `oct-status` as "Required". Report: both decisions and the confirmation. From then on strikes escalate.

## Spec coverage

| Spec section | Task |
|---|---|
| 1 goal, success criteria | all; acceptance lines per milestone |
| 3 decisions | Tasks 8, 12, 16, 17, 20 |
| 4 model, labels, relations | Tasks 1, 3, 6, 8 |
| 5 block, overwrite protection | Tasks 9, 10, 16 |
| 5a guide comment | Tasks 9, 10, 12 |
| 6 derivation | Task 8 |
| 7 actors, Gitar | Tasks 1, 8, 14, 17, 19 |
| 8 agent enforcement | Tasks 15, 16 |
| 9 labels and migration | Tasks 3, 4, 5 |
| 10 escalation | Task 13 |
| 11 commands | Task 12 |
| 12 components, workflow | Tasks 5, 11, 14 |
| 13 documentation | Task 18 |
| 14 tests, rollout | per-task tests; milestones 0-4; existing suites in CI: Tasks 2a-2d |
| 15 open points | Tasks 15, 19, 20 |
| 16 DoR/DoD | Global Constraints, milestone = spec issue |
