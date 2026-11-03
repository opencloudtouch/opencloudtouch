# OCT checklist interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a human operate the OCT status workflow by clicking checkboxes in a bot-managed "Workflow" zone of the description (the system ticks what it can know itself), with required, optional and overridden steps, as a second trigger beside the `/oct` commands.

**Architecture:** A step catalog (`checklist.yml`) drives a zone in the description below the status block. The zone is a projection of the state, rendered on every run. A description edit is parsed into a tick diff; each toggled manual step runs through the existing `commands.execute` path with the editor as actor. Dashboard issue and gate come last. Nothing blocks until `checklist.gate` is switched on.

**Tech Stack:** Python 3.11+ (`scripts/oct_status`, stdlib + httpx + PyYAML as today), pytest, GitHub Actions workflow `oct-status.yml`.

**Spec:** `docs/superpowers/specs/2026-10-31-oct-checklist-design.md`. It extends `docs/superpowers/specs/2026-10-29-oct-status-system-design.md`; the earlier plan is `docs/superpowers/plans/2026-10-30-oct-status-system.md`.

## Global Constraints

- All text the system writes (zone lines, reasons, dashboard) is English; chat with the user is German; commit messages, code, comments and docs are English (`CLAUDE.md`).
- Commits: Conventional Commits, no attribution trailers, no references to AI tools, never `--no-verify`.
- Work on a branch started from `main` after pull request 584 is merged (a merged pull request is never reused). Tests: `cd scripts/oct_status && python -m pytest -q --cov=.` with coverage at least 90 %, `ruff check .`, `ruff format --check .`, `mypy .`, `python scripts/check-mojibake.py .`, `actionlint` for workflow edits, and `tests/test_docs_snippets.py` green.
- Markers: zone `<!-- oct-checklist:v1 -->` ... `<!-- /oct-checklist -->`, step marker `<!-- oct:step=<id> -->` or `<!-- oct:step=<id> auto -->`. The status block markers and the guide marker `<!-- oct-next:v1 -->` are unchanged.
- The zone sits directly below the status block (at the top when there is none), has at most ten lines, and never exceeds the description limit of 65,000 characters.
- Required and optional come from the catalog, never from the text. Automatic steps are rewritten on every run. A manual step is ticked exactly when its state holds; ticks have no memory of their own.
- A tick has the effect of its command: same authorization (write for `review`, `ready`, `rework`, `approve`, `no-spec`; maintain or admin for `triage`, `confirm`, `verified`, `override`, `accept-paths`), same state machine check, same outcome. Fail closed on every lookup error. Bots and automation never tick.
- Shadow mode (`OCT_STATUS_WRITE` unset): nothing is written; the zone appears in the job summary. The read-only API refuses every other write.
- No new blocking: `checklist.gate` defaults to `off`; strikes stay off.
- Texts of untrusted origin (reasons, titles) go through the existing neutralising (`guide._safe`, `notices.scrub`, `render._cell`).

## Review Focus

1. A tick by a person without write access (author of a fork pull request): reverted, no state change, reason shown.
2. A damaged or duplicated zone (deleted marker, two zones, unknown step id): no tick is inferred, the zone is rebuilt from the state, a warning reaches the summary.
3. Two ticks in one edit, one valid and one rejected: the valid one applies, the other is reverted with its own reason.
4. A click and a bot write overlapping: the click is judged against the old description of its own event; the bot's rewrite neither loses nor repeats it.
5. A contributor pastes `<!-- oct:step=approval -->` or a whole zone into free text outside the zone: ignored; only the first zone below the status block counts.
6. CRLF descriptions and descriptions near 65,000 characters: the zone splice keeps line endings and never truncates the user's text.
7. A hooked agent session ticks a maintainer step (body carries `<!-- oct-src:1 -->`): rejected on the server and denied by the hook.

## File Structure

| File | Responsibility |
|---|---|
| `scripts/oct_status/checklist.yml` | step catalog per artifact kind (English texts) |
| `scripts/oct_status/checklist.py` | `StepDef`, `Catalog`, `load_catalog`, `ChecklistLine`, `build_lines`, automatic derivations |
| `scripts/oct_status/zone.py` | render, parse and splice of the zone |
| `scripts/oct_status/ticks.py` | `Tick`, `tick_diff`, `apply_tick`, undo and toggle mapping |
| `scripts/oct_status/dashboard.py` | dashboard issue model, render, tick processing (milestone 4) |
| `scripts/oct_status/notices.py` | guide data gets acknowledgements (`Ack`) |
| `scripts/oct_status/main.py` | wiring in `run_event`, `run_audit`, gate; kept thin, logic stays in the modules above |
| `scripts/oct_status/hooks/guard.py` | deny maintainer-step ticks by agents |
| `scripts/oct_status/tools/render_doc_snippets.py`, `docs/WORKFLOW.md` | golden zone snippets and handbook text |

---

# Milestone 1 - Catalog and zone (shadow, no manual ticks)

### Task 1: Step catalog

**Files:**
- Create: `scripts/oct_status/checklist.yml`, `scripts/oct_status/checklist.py`, `scripts/oct_status/tests/test_checklist_catalog.py`
- Modify: `scripts/oct_status/config.py` (field `checklist_gate: Literal["off", "required"] = "off"`), `scripts/oct_status/config.yml` (`checklist_gate: off`)

**Interfaces:**
- Produces: `StepDef(id: str, text: str, requirement: Literal["required","optional"], required_if: str | None, mode: Literal["auto","manual","toggle"], auto: str | None, command: str | None, min_permission: Literal["write","maintain"], distinct_from_author: bool, visible_in: tuple[str, ...])`; `Catalog.steps_for(kind: Kind, phase: Phase) -> tuple[StepDef, ...]`; `load_catalog(path: Path) -> Catalog`.

- [ ] **Step 1: Write the failing tests** `test_catalog_covers_every_workflow_command`: every name in `commands.COMMANDS` except `override` and `supersede` is the `command` of at least one manual or toggle step; `test_min_permission_defaults_to_command_level`: a step whose command is in `commands.MAINTAINER_COMMANDS` loads with `maintain`, the others with `write`; `test_catalog_rejects_unknown_mode_duplicate_id_and_missing_command` (each raises `ValueError`); `test_spec_and_pull_request_steps_match_the_spec_tables` (ids and modes of the two tables in spec section 2.3 for kinds SPEC and PULL_REQUEST); `test_steps_for_filters_by_phase`; `test_distinct_from_author_defaults_to_false_and_is_loaded` (the flag of spec section 2.7, off for `reviewed`).
- [ ] **Step 2: Run** `python -m pytest tests/test_checklist_catalog.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** the dataclasses and `load_catalog` in `checklist.py`, and write `checklist.yml` with the steps of spec section 2.3 (ids: `dor`, `submitted`, `reviewed`, `implementing`, `merged`, `device-test`, `closed`, `spec-linked`, `no-spec`, `template`, `prerequisite`, `ci`, `findings`, `protected-paths`, `approval`, `triaged`, `confirmed`, `wait-reporter`, `wait-designer`, `wait-hardware`, `override`). The `override` step is `manual`, `maintain`, command `override`, on every kind.
- [ ] **Step 4: Run** the tests, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add the checklist step catalog`.

### Task 2: Automatic steps and step state

**Files:**
- Modify: `scripts/oct_status/checklist.py`; Test: `scripts/oct_status/tests/test_checklist_state.py`

**Interfaces:**
- Consumes: `rules.dor_status`, `rules.protected_changes` and the template check already used by V05 (`violations`), `Derived`, `Graph`, `notices.GuideState`.
- Produces: `ChecklistLine(step: StepDef, ticked: bool, required: bool, skipped: bool, reason: str)`; `build_lines(snap: Snapshot, derived: Derived, graph: Graph, cfg: Config, catalog: Catalog, state: GuideState | None) -> list[ChecklistLine]`.

- [ ] **Step 1: Write the failing tests**: one test per automatic step with a minimal snapshot that makes it true and a variant that makes it false (`dor`, `implementing`, `merged`, `closed`, `spec-linked`, `template`, `prerequisite`, `ci`, `findings`); `test_manual_steps_derive_from_labels_and_guide_data` (`submitted` from `phase:spec-review`, `reviewed` from `phase:ready`, `triaged` from `phase:triaged`, `wait-reporter` from the label, `protected-paths` from `GuideState.accepted`); `test_required_if_hardware_follows_the_wait_label`; `test_unreadable_guide_state_ticks_no_manual_step` (state `None`); `test_overridden_required_steps_are_skipped`.
- [ ] **Step 2: Run** the file. Expected: FAIL.
- [ ] **Step 3: Implement** `build_lines`; the automatic derivations are small functions registered by the `auto` name in the catalog (reuse the rule functions, do not copy them). `skipped` comes from the `skipped` acknowledgement added in Task 6; until then it is always false.
- [ ] **Step 4: Run** tests, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): derive checklist lines from the state`.

### Task 3: The zone

**Files:**
- Create: `scripts/oct_status/zone.py`, `scripts/oct_status/tests/test_zone.py`

**Interfaces:**
- Consumes: `ChecklistLine`, `render.splice_block` rules for CRLF and limits.
- Produces: `render_zone(phase_line: str, lines: list[ChecklistLine]) -> str`; `parse_zone(body: str) -> list[ParsedLine] | None` with `ParsedLine(step_id: str, ticked: bool, auto: bool, text: str)`; `splice_zone(body: str, zone: str | None, limit: int = 65_000) -> str` (`None` removes the zone).

- [ ] **Step 1: Write the failing tests**: `test_render_marks_required_optional_auto_and_skipped` (`(required)`, `(optional)`, `(auto)`, `(skipped)` suffixes and `[x]`/`[ ]`); `test_zone_sits_below_the_status_block_and_at_the_top_without_one`; `test_splice_is_idempotent`; `test_splice_keeps_crlf`; `test_splice_never_truncates_user_text_near_the_limit` (returns the body unchanged and the zone is dropped); `test_parse_takes_only_the_first_zone_and_ignores_markers_in_free_text`; `test_parse_returns_none_for_missing_end_marker`; `test_hostile_text_is_neutralised` (mentions, links, `<!--` in a reason).
- [ ] **Step 2: Run** the file. Expected: FAIL.
- [ ] **Step 3: Implement** the three functions; a zone has at most ten lines (extra optional steps collapse into one summary line "and n more").
- [ ] **Step 4: Run** tests, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): render, parse and splice the checklist zone`.

### Task 4: Shadow rendering in the event pipeline

**Files:**
- Modify: `scripts/oct_status/main.py` (`_converge`, `run_audit`), `scripts/oct_status/apply.py`, `scripts/oct_status/violations.py`, `scripts/oct_status/hooks/guard.py`, `scripts/oct_status/tools/render_doc_snippets.py`; Test: `tests/test_main_checklist.py`, `tests/test_hooks.py`, `tests/test_violations.py`

**Interfaces:**
- Consumes: `build_lines`, `render_zone`, `splice_zone`, `Workspace`, `apply_state`.
- Produces: `apply_state(..., zone: str | None)` writes the zone together with the block in write mode; the dry-run summary prints the zone.

- [ ] **Step 1: Write the failing tests**: `test_dry_run_prints_the_zone_and_writes_nothing` (read-only API raises on any write); `test_write_mode_splices_zone_with_the_block_in_one_patch`; `test_zone_edit_is_not_a_status_block_violation` (V03 ignores the zone); `test_hook_block_splice_keeps_the_zone` (`guard.decide` for a description write keeps the existing zone intact); `test_second_run_writes_nothing`.
- [ ] **Step 2: Run** the three files. Expected: FAIL.
- [ ] **Step 3: Implement** the wiring: `_converge` builds the lines (Task 2), renders the zone and passes it to `apply_state`; `apply_state` compares the spliced body (block and zone) before patching; the audit does the same per artifact; the guard's splice and `violations` V03 learn the zone region; the doc snippet tool gets a `zone-*` snippet family (used in Task 11).
- [ ] **Step 4: Run** the full suite, `ruff`, `mypy`, `actionlint`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): show the workflow checklist zone`.

**Milestone 1 acceptance:** with write mode off, the job summary of every run lists the zone; with write mode on, descriptions carry it and a second run writes nothing. **MAINTAINER ACTION MA-10** (after the merge of this milestone, shadow mode is enough): verify that GitHub sends the previous description on a checkbox click. Do: open a throwaway pull request, click any box of the pasted example list `- [ ] a` in its description, open the `OCT Status` run for that `edited` event and read the line "description edited: previous text present: yes/no" in the summary (Task 5 adds it). Report the answer; if "no", milestone 2 is redesigned around a snapshot of the zone kept in the guide data.

---

# Milestone 2 - Manual ticks

### Task 5: Tick diff

**Files:**
- Create: `scripts/oct_status/ticks.py`, `scripts/oct_status/tests/test_tick_diff.py`
- Modify: `scripts/oct_status/main.py` (summary line "description edited: previous text present: yes/no")

**Interfaces:**
- Consumes: `zone.parse_zone`.
- Produces: `Tick(step_id: str, ticked: bool, text: str = "")` (`text` is the override reason after `reason:`); `tick_diff(old_body: str, new_body: str) -> list[Tick]`.

- [ ] **Step 1: Write the failing tests**: tick and untick of one step; two steps in one edit; edit outside the zone gives `[]`; damaged, missing or duplicated zone gives `[]`; unknown step id is ignored; the override line with a reason yields `Tick("override", True, "reason text")`; an edit that changes only the visible `(required)` suffix gives `[]`; CRLF old text against LF new text.
- [ ] **Step 2: Run** the file. Expected: FAIL.
- [ ] **Step 3: Implement** `tick_diff` by comparing the `ticked` flag per step id of the two parsed zones.
- [ ] **Step 4: Run** tests, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): detect ticks in edited descriptions`.

### Task 6: Applying ticks

**Files:**
- Modify: `scripts/oct_status/ticks.py`, `scripts/oct_status/notices.py` (acknowledgements); Test: `tests/test_tick_apply.py`, `tests/test_notices.py`

**Interfaces:**
- Consumes: `commands.execute`, `commands.authorize_detailed`-style permission lookup (`_permission`), `Catalog`, `GuideState`.
- Produces: `Ack(step: str, login: str, time: datetime, sha: str, reason: str)` in `GuideState.acks` (cap 20, scrubbed, validated like the other records); `TickOutcome(ok: bool, message: str, declare: dict[str, list[str]], ack: Ack | None, revert: bool)`; `async apply_tick(api: GitHubApi, snap: Snapshot, derived: Derived | None, tick: Tick, sender: str, cfg: Config, catalog: Catalog, *, dry_run: bool, now: datetime) -> TickOutcome`.

- [ ] **Step 1: Write the failing tests**: for each manual step, `test_tick_equals_command` (the `declare` of `apply_tick` equals the `declare` of `execute` for the matching `Command`); `test_tick_without_write_permission_is_reverted`; `test_maintain_steps_need_maintain` (`verified`, `triage`, `confirm`, `accept-paths`); `test_permission_lookup_error_reverts_with_reason` ("permission could not be verified"); `test_bot_sender_is_ignored`; `test_rejected_precondition_is_reverted_with_the_reason_and_marks_v07` (`Outcome.precondition`); `test_untick_runs_the_inverse_transition` ("Reviewed" off runs `rework` with the reason "unchecked"); `test_untick_without_inverse_is_restored_with_the_command_named`; `test_toggle_sets_and_clears_the_wait`; `test_override_skips_required_steps_and_records_reason` (an `Ack` with `step="override"`); `test_approval_ack_is_bound_to_the_head_sha`; `test_dry_run_writes_nothing`.
- [ ] **Step 2: Run** the files. Expected: FAIL.
- [ ] **Step 3: Implement** `apply_tick`: map the step's `command` and the tick to a `Command`, authorize with the step's `min_permission`, call `execute`; map `Outcome` to `TickOutcome`; extend `notices.parse_state` and `state_data` with `acks`; `checklist.build_lines` reads `acks` (`skipped`, `approval`).
- [ ] **Step 4: Run** tests, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): apply checklist ticks like their commands`.

### Task 7: Event wiring and agent defence

**Files:**
- Modify: `scripts/oct_status/main.py` (`run_event`, new `_handle_ticks`), `scripts/oct_status/apply.py` (`is_own_event`), `scripts/oct_status/hooks/guard.py`; Test: `tests/test_main_ticks.py`, `tests/test_hooks.py`

**Interfaces:**
- Consumes: `tick_diff`, `apply_tick`, `commands.AGENT_MARKER`, `Workspace`.
- Produces: `async _handle_ticks(ws: Workspace, number: int, payload: dict[str, Any], dry_run: bool, clock: Callable[[], datetime]) -> TickReport | None`; the guard denies a description write whose zone changes a maintainer-level step.

- [ ] **Step 1: Write the failing tests**: `test_edited_event_ticks_through_run_event` (an `issues` `edited` payload with `changes.body.from` ticks `submitted` and the label appears; the rewritten zone follows); `test_tick_in_a_body_with_the_agent_marker_is_rejected_for_maintainer_steps`; `test_forged_tick_of_an_automatic_step_is_restored`; `test_two_ticks_one_invalid`; `test_own_edit_does_not_loop` (`is_own_event`); `test_rejection_reason_is_written_behind_the_line`; `test_hook_denies_maintainer_step_tick_in_a_description_write`; `test_catalog_maintain_steps_match_the_hook_list` (parity).
- [ ] **Step 2: Run** the files. Expected: FAIL.
- [ ] **Step 3: Implement** `_handle_ticks` and call it for `issues` and `pull_request_target` events with action `edited`; revert and reasons are written with the zone in the same description write as the block; the guard reads the current zone through its REST context and compares ticks of the proposed body.
- [ ] **Step 4: Run** the full suite, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): process checklist ticks from edited descriptions`.

### Task 8: Approval step

**Files:**
- Modify: `scripts/oct_status/checklist.py`, `scripts/oct_status/rules.py` (reuse `_approved`); Test: `tests/test_checklist_approval.py`

- [ ] **Step 1: Write the failing tests**: `test_approval_is_ticked_when_an_allowed_review_approved_the_current_head`; `test_new_push_clears_the_approval_tick_except_formatter_bot`; `test_maintainer_may_tick_approval_on_own_pull_request`; `test_other_authors_still_need_a_person_with_association`; `test_tick_stores_login_time_and_sha`.
- [ ] **Step 2: Run** the file. Expected: FAIL.
- [ ] **Step 3: Implement** the `approval` derivation: ticked when the existing approval rule holds, or when an `Ack(step="approval")` carries the current head sha.
- [ ] **Step 4: Run** tests, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): tie the approval step to the head commit`.

---

# Milestone 3 - Handbook and guide

### Task 9: Slimmer guide

**Files:**
- Modify: `scripts/oct_status/guide.py`, `scripts/oct_status/tests/fixtures/golden/*.md`; Test: `tests/test_guide.py`

- [ ] **Step 1: Write the failing tests**: `test_next_steps_refer_to_checklist_lines` (a step says "Tick Approval in the Workflow list", the command stays in a collapsed section); `test_commands_valid_now_moves_into_a_collapsed_details_for_automation`.
- [ ] **Step 2: Run** `tests/test_guide.py`. Expected: FAIL.
- [ ] **Step 3: Implement** in `guide.next_steps` and `render_guide`: step text names the checklist line when the catalog has one; "Commands valid now" is rendered inside `<details>`. Regenerate the golden files with the tool and review the diff.
- [ ] **Step 4: Run** the suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): point the guide at the checklist`.

### Task 10: Handbook and template pointer

**Files:**
- Modify: `docs/WORKFLOW.md`, `scripts/oct_status/tools/render_doc_snippets.py`, `.github/pull_request_template.md` (one pointer line), `CLAUDE.md` (one bullet in "Status system"); Test: `tests/test_docs_snippets.py`, `tests/test_repo_files.py`

- [ ] **Step 1: Write the failing tests**: `test_zone_snippets_match_the_renderer` for a spec, a pull request, a bug and a Dependabot pull request (snippet names `zone-spec`, `zone-pr`, `zone-bug`, `zone-dependabot`); `test_handbook_documents_every_catalog_step` (each step id and text appears in the step reference table); `test_template_points_to_the_zone`.
- [ ] **Step 2: Run** the files. Expected: FAIL.
- [ ] **Step 3: Write** the handbook sections: "The workflow zone" (what is ticked by whom), step reference per kind, required, optional and override, ticks versus commands, troubleshooting (a reverted tick shows its reason), the gate switch. Walkthrough snippets are rendered from fixtures, not typed.
- [ ] **Step 4: Run** the suite and the mojibake check. Expected: PASS.
- [ ] **Step 5: Commit** `docs: document the workflow checklist`.

---

# Milestone 4 - Dashboard and gate

### Task 11: Dashboard issue

**Files:**
- Create: `scripts/oct_status/dashboard.py`, `scripts/oct_status/tests/test_dashboard.py`
- Modify: `scripts/oct_status/main.py` (`run_audit`, `run_event`), `scripts/oct_status/apply.py` (`is_own_event`), `scripts/oct_status/config.yml`

**Interfaces:**
- Consumes: snapshots, `Derived`, `build_lines`, `apply_tick`, `config.bot_logins`.
- Produces: `build_dashboard(snaps: dict[int, Snapshot], derived: dict[int, Derived], cfg: Config, catalog: Catalog) -> Dashboard`; `render_dashboard(d: Dashboard) -> str`; `parse_actions(old: str, new: str) -> list[tuple[int, str]]` (artifact number, step id of a ticked action line); `async ensure_dashboard(api: GitHubApi, cfg: Config, *, dry_run: bool) -> int`.

- [ ] **Step 1: Write the failing tests**: sections "Waiting for you", "Waiting for others", "Violations and blockers", "Automation pushes to review" with the right artifacts; action lines carry a stable marker `<!-- oct:action=<number>:<step> -->`; `test_dashboard_is_found_by_title_and_bot_creator_only` (a stranger's issue with the same title is ignored); `test_dashboard_tick_acts_as_the_tick_in_the_artifact` (same permission checks, actor is the editor); `test_dashboard_edit_by_a_person_without_write_is_reverted`; `test_dry_run_writes_nothing`; `test_dashboard_has_no_labels_and_no_block`.
- [ ] **Step 2: Run** the file. Expected: FAIL.
- [ ] **Step 3: Implement** the module; the dashboard issue is created by `oct-support` in write mode only, refreshed by events that change a listed artifact and by the nightly audit; the maintainer pins it once by hand.
- [ ] **Step 4: Run** the suite, `ruff`, `mypy`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add the dashboard issue`.

### Task 12: Gate switch

**Files:**
- Modify: `scripts/oct_status/main.py` (`gate_problems`), `docs/WORKFLOW.md`, `docs/superpowers/plans/2026-10-30-oct-status-system.md` (MA-9 gets a third decision); Test: `tests/test_main_checklist.py`

- [ ] **Step 1: Write the failing tests**: `test_gate_off_never_fails_for_open_required_steps`; `test_gate_required_fails_for_an_open_required_step_and_names_it`; `test_overridden_required_steps_do_not_fail`; `test_status_description_names_the_first_open_step`.
- [ ] **Step 2: Run** the file. Expected: FAIL.
- [ ] **Step 3: Implement** the check in `gate_problems` behind `cfg.checklist_gate`; keep the default `off` in `config.yml` and a test that pins it.
- [ ] **Step 4: Run** the suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(oct-status): add the checklist gate switch (off)`.

**Final acceptance:** all four milestones merged, `checklist_gate: off`, strikes unchanged. A whole-branch review (fresh reviewer, most capable model) checks the Review Focus list and the spec's success criteria.

---

## Maintainer actions

**MA-10 - Check the previous description on a checkbox click.** When: after Task 4 is merged (shadow mode is enough). Why: ticks are detected by comparing the previous description with the new one; if GitHub does not send the previous text for a click, milestone 2 needs another design. Do: open a throwaway pull request, add `- [ ] a` to its description, click the box, open the `OCT Status` run of the `edited` event and read the summary line. Report: "yes" or "no". Close the pull request afterwards.

**MA-9 (extended).** The decision list of MA-9 gets a third item: whether `checklist_gate` stays `off` or becomes `required`. Task 12 adds it to the plan text.

## Spec coverage

| Spec section | Task |
|---|---|
| 2.1 zone | 3, 4 |
| 2.2 catalog | 1 |
| 2.3 steps per kind | 1, 2 |
| 2.4 state is a projection, guide data | 2, 6 |
| 2.5 tick processing | 5, 6, 7 |
| 2.6 approval | 8 |
| 2.7 independent review | 1 (catalog flag), 6 |
| 3 security and failure | 6, 7 and the Review Focus tests |
| 4 gate | 12 |
| 5 dashboard issue | 11 |
| 6 milestones, 7 tests, 9 risks | milestones above, MA-10 |
