# OCT status system: checklist interface

Status: design for review, 2026-10-31. Extends `2026-10-29-oct-status-system-design.md` (the "status
system spec"); nothing in that design is replaced.

## 1. Intent

The status system derives phase, waits and violations from facts and shows them through labels, a status
block and one guide comment. Humans move a workflow forward with `/oct` commands in comments. That works
for automation and agents; for the one maintainer of this repository it is too much typing for too little
gain.

**Goal.** A human can operate the workflow by clicking checkboxes. The system ticks what it can know
itself; a human ticks only what only a human can know. Required and optional steps are visible, a required
step can be overridden with a reason, and nothing blocks anybody until the project has seen how the
system behaves in practice.

**Who it is for.** The maintainer (alone today, more later) and contributors with write access. Authors
without write access cannot tick workflow steps.

**What stays.** The state machine, the fact derivation, the violation catalogue V01 to V08, the strike
ledger, the `/oct` commands, the labels and the status commit status. Checkboxes are a **second trigger**
with the same effect as the matching command. Commands remain the interface for automation and agents.

**Success criteria.**

1. Every `/oct` command that moves the workflow has a checkbox equivalent, and a tick takes the same code
   path as the command (same authorization, same state machine check, same outcome).
2. A step the system can determine from facts is never ticked by a human; the system ticks it.
3. Required, optional and overridden steps are distinguishable at a glance.
4. A forged or invalid tick has no effect; the reason is shown on the line.
5. In shadow mode nothing is written; with `OCT_STATUS_WRITE` unset the checklist appears in the job
   summary only.
6. No new blocking behaviour: an open required step does not make `oct-status` red until
   `checklist.gate` is switched on.

**Inspiration.** Renovate's Dependency Dashboard (a bot-maintained issue whose checkboxes trigger actions)
and task-list checker actions (a check that is pending until required boxes are ticked, with markers for
optional items). The opposite model, command-driven chat-ops (Kubernetes Prow `/lgtm`, `/approve`), is
what the status system already offers and what this design makes optional for humans.

**Language.** All text the system writes (zone lines, reasons, dashboard) is English, like the rest of
the repository (`CLAUDE.md`). The texts live in one file (the step catalog), so a translation could be
added there later; none is built.

## 2. Concept

### 2.1 The checklist zone

The description of an issue or pull request gets a second bot-managed region directly below the status
block:

```
<!-- oct-status:v1 hash=... -->  ... status block, read-only for humans (V03) ...  <!-- /oct-status -->
<!-- oct-checklist:v1 -->
## Workflow
Phase **in-review**, waiting on: you.

- [x] Spec linked: #600 <!-- oct:step=spec-linked auto -->
- [x] Pull request template complete <!-- oct:step=template auto -->
- [x] CI green <!-- oct:step=ci auto -->
- [ ] Approval (required) <!-- oct:step=approval -->
- [ ] Hardware test on a device (optional) <!-- oct:step=hardware-test -->
- [ ] Skip required steps, reason: <!-- oct:step=override -->
<!-- /oct-checklist -->
```

- The zone is the first bot-managed region that humans may edit. Editing the status block is still V03;
  deleting or damaging the zone is **not** a violation: it is rebuilt from the state.
- Each line carries a hidden marker with a stable step id and, for steps the system ticks itself, the word
  `auto`. Humans never type markers; the visible suffixes `(required)` and `(optional)` come from the
  catalog, not from the text, so editing them has no effect.
- The pull request template keeps its own definition of ready and definition of done checklists; they
  are not part of the zone and are not ticked by the system (V05 still guards their deletion).

### 2.2 Step catalog

`scripts/oct_status/checklist.yml` is the single source for steps. Per artifact kind (spec, bug, feature
request, tracking, test plan, pull request, docs pull request, dependency pull request) it lists:

| Field | Meaning |
|---|---|
| `id` | stable identifier (marker, ledger, guide data) |
| `text` | the English line |
| `requirement` | `required`, `optional`, or `required_if: <condition>` (for example hardware affected) |
| `mode` | `auto` (derived from facts) or `manual` (a human ticks) or `toggle` (a manual switch for a wait) |
| `auto` | for `auto` steps: the derivation (names a function over the snapshot) |
| `command` | for `manual` and `toggle` steps: the equivalent `/oct` command |
| `min_permission` | `write` or `maintain`, defaults to the permission of the command |
| `visible_in` | phases in which the step is shown |

Parity is tested: the catalog covers every command of `commands.COMMANDS` that moves the workflow, and
a tick calls the same `execute` path as the command.

### 2.3 Steps per kind (initial catalog)

A = auto, M = manual, T = toggle, R = required, O = optional.

**Spec**

| Step | Mode | Requirement | Equivalent |
|---|---|---|---|
| Definition of ready complete | A | R | `dor_status` |
| Submitted for review | M | R | `/oct review` |
| Reviewed, ready to implement (text: "Reviewed by: login") | M | R | `/oct ready --reviewer ...` |
| Implementation started (linked pull request open) | A | O | fact phase `in-progress` |
| All pull requests merged | A | O | fact phase `verification` |
| Verified on a device | M | R if hardware is affected, else O | `/oct verified` |
| Closed | A | O | closed |

**Pull request** (also docs and dependency pull requests, without the spec step)

| Step | Mode | Requirement | Equivalent |
|---|---|---|---|
| Spec linked (`Part of` / `Closes`) | A | R | V01 |
| No spec needed, reason: ... | M | O | `/oct no-spec` (replaces "Spec linked") |
| Pull request template complete | A | R | V05 |
| Prerequisite merged or stacked on | A | R | V04 |
| CI green | A | R | `wait:ci` |
| Findings resolved | A | R | `wait:findings` |
| Protected paths reviewed (only when automation pushed there) | M | R | `/oct accept-paths` |
| Approval | M | R | `/oct approve` and the review |
| Verified on a device | M | R or O | `/oct verified` |

**Bug and feature request:** "Triaged" (M, R, `/oct triage`), "Confirmed" (M, R, bug only, `/oct confirm`).

**Toggles** (all kinds, M, O): "Waiting for the reporter" (`wait:reporter`, `/oct needs-info`), "Design
needed" (`wait:designer`), "Hardware test needed" (`wait:hardware-test`). Ticking sets the wait,
unticking clears it.

**Override line** (all kinds, M, O, maintain): "Skip required steps, reason: ...". It marks every open
required step as skipped; the reason is written to the history of the guide. It is the checkbox form of
`/oct override` for the checklist and does not clear violation notices.

The catalog is deliberately small. Steps that daily work shows to be missing are added to the catalog.

### 2.4 State stays a projection

The zone is derived from the state on every run, like the status block: a manual step is ticked exactly
when the state it stands for holds (a declaration label, a cleared wait, or an entry in the guide data).
Ticks have no memory of their own. A tick is an **input**; after it is processed, the zone is rendered
again from the new state.

Where a step has no label, its state is stored in the guide data (the bot-owned JSON of the guide
comment, protected against forgery as designed in the status system spec): `approval` (login, time,
head sha), `protected-paths` (as today), `skipped` (steps, login, time, reason).

### 2.5 Tick processing

1. Triggers: `issues.edited` and `pull_request_target.edited` (already subscribed). The event carries the
   old description (`changes.body.from`) and the sender.
2. Parse the zone of the old and the new description; the difference is the list of toggled steps. Edits
   outside the zone are ordinary description edits. An edit that damages the zone yields no tick
   (the zone is rebuilt).
3. For each toggled **manual or toggle** step: authorize the sender (write permission through the
   collaborator API; fail closed on any error; bots and automation are ignored; the permission level is
   the step's `min_permission`). Run the equivalent `execute` of the command with the sender as actor.
4. Toggled **auto** steps are ignored; the next render restores them.
5. Outcome: accepted ticks are applied through the same declaration path as the command (label changes,
   guide data). A rejected tick is reverted in the zone and the reason is written behind the line
   (`⚠ Definition of ready incomplete`). A rejection that a command reports as an invalid declaration is
   violation V07 for the sender exactly as for the command (a hint only while strikes are off).
6. Untick: allowed where the state machine has a legal inverse (for example "Reviewed" off runs the
   `/oct rework` transition with the reason "unchecked"; toggles switch off). Otherwise the tick is
   restored and the line names the command.
7. The own-event guard ignores the bot's own description edits, so a rewrite does not loop.

### 2.6 Approval

"Approval" is bound to the head commit, like approvals today: a new push by anybody but `formatter-bot`
clears the tick. The system also ticks "Approval" itself when `oct-support` or another person with write
access approved the current head. On a pull request of the maintainer, ticking is allowed for the
maintainer. This relaxes nothing in the approval rules for other authors: they still need an approval by a
person with OWNER, MEMBER or COLLABORATOR association.

### 2.7 The independent review of a spec

`CLAUDE.md` requires a spec to be reviewed by someone other than its author or by independent reviewers; the third party may be a person or an AI reviewer running in a fresh session that did not write the spec, with its findings recorded in the issue.
The checklist does not check the author against the reviewer any more (a tick is valid from any person with
write access). The line "Reviewed, ready to implement" carries the hint "review by a third party or an
independent reviewer, else skip with a reason", and the name of whoever ticked is written to the history.
The commands keep their stricter check; this relaxation applies to ticks only and can be tightened in the
catalog (`min_permission`, a catalog flag `distinct_from_author`).

## 3. Security and failure

- **Scope of trust.** Only the zone accepts human edits as input. The status block, the guide comment and
  the ledger keep their protections. A description edit by somebody without write access (for example the
  author of a fork pull request) changes no workflow state; their ticks are reverted.
- **Agents.** The agent hooks deny description writes that change ticks of maintainer-level steps and
  append the source marker to other writes; the server rejects ticks of maintainer-level steps in a
  description that carries the marker, exactly as for commands. A hooked session may tick no step that
  its command equivalent forbids.
- **Automatic steps cannot be forged:** they are overwritten on every run.
- **Concurrency.** A click and a bot run can overlap. The applier already re-reads the description before
  writing and merges the block; it does the same for the zone, and a tick that was in flight is compared
  with the old description of its own event, not with the latest state.
- **Failure.** If the zone cannot be parsed, the system treats the event as no tick, rebuilds the zone
  from the state and writes a warning to the job summary. If the collaborator permission lookup fails,
  the tick is reverted with the reason "permission could not be verified".
- **Shadow mode.** The zone is rendered into the job summary only; `OCT_STATUS_WRITE` gates the write, and
  the read-only API refuses every other write.
- **Strikes.** Unchanged. A tick rejected for a failed precondition counts like the command would.

## 4. Gate

`checklist.gate` in `config.yml` has the values `off` (default) and `required`. With `required`, an open
required step (not overridden) is a problem of the gate and makes the commit status `oct-status` fail.
Nothing in this design switches it on; the maintainer decides after some weeks of use (maintainer action
MA-9 gets a third decision).

## 5. Dashboard issue (milestone 4)

One pinned issue "OCT Dashboard", written by the bot and treated as automation content (no labels, no
block), listing what needs attention:

- **Waiting for you:** approvals, triage, spec reviews, device tests, protected paths to review.
- **Waiting for others:** reporter, designer.
- **Violations and blockers.**
- **Automation pushes to review.**

Every line links to the artifact and may carry an action checkbox ("Approve #574"). Ticking it acts as
the tick in the artifact, with the same rights and checks; the actor is the editor of the dashboard.
The dashboard is refreshed on events and by the nightly audit and replaces the filter links of
`docs/WORKFLOW.md`. The same tick processing is reused (`issues.edited` on the dashboard issue), with the
same protections against edits by people without write access.

## 6. Milestones

1. **Catalog and zone.** `checklist.yml`, parser and renderer for the zone, automatic steps, shadow
   rendering into the job summary. No manual ticks yet.
2. **Manual ticks.** Tick diff, authorization, rejection with reason, undo, approval bound to the head,
   toggles, override line, hooks and server defence for agents, V07 mapping.
3. **Handbook and guide.** `docs/WORKFLOW.md` with golden-tested zone snippets from real artifacts; the
   guide drops the command lists for humans ("Next steps" stays); the pull request template points to
   the zone.
4. **Dashboard issue.**

Strikes and `checklist.gate` stay off throughout.

## 7. Tests

- Golden snippets of the zone for a spec, a pull request, a bug and a Dependabot pull request, rendered by
  the doc snippet tool and compared by the docs test.
- Unit tests of the tick diff: every step, ticks, unticks, damaged zone, edits outside the zone.
- Every rejection and every undo path; parity between the catalog and `commands.COMMANDS`; a tick and the
  command give the same label changes.
- Forged ticks: no write permission, bot sender, agent source marker on a maintainer step, tick of an
  automatic step, lookup error.
- Concurrency: tick during a bot write, bot rewrite after a tick, own-event guard.
- Shadow mode: nothing is written (read-only API), summary contains the zone.
- Hooks: parity of the maintainer-step list with the catalog.

## 8. Not in scope

- Changes to the state machine, the V01 to V08 catalogue, the ledger or the commands.
- Automatic ticks in the definition of ready and definition of done lists of the pull request template.
- Translations of the zone texts.
- Switching the gate or strikes on.

## 9. Risks and points to verify

- **GitHub task list toggling.** The web interface may rewrite the whole description when a box is
  clicked; the edit event must carry the previous text. To verify on a throwaway pull request before
  milestone 2 (event payload `changes.body.from`, concurrent edits).
- **Description noise.** A second managed region lengthens every description; the zone is short (at most
  ten lines) and collapses to the phase line when nothing is open.
- **Relaxed independence rule (2.7)** conflicts with `CLAUDE.md` unless used with the hint and the
  override; the maintainer accepts it for ticks.
- **Two checklists in one description** (the zone and the template's lists). The zone sits above the
  template and is labelled "Workflow"; observation in daily use decides whether to merge them later.
- **Permission lookups** cost one API call per tick and per run that sees a tick.
