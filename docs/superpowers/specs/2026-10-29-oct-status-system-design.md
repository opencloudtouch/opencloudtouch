# OCT Status System - Design

Status: draft for maintainer review. Date: 2026-10-29.

## 1. Goal

Every GitHub artifact (issue, pull request, discussion) shows, at a glance:

1. its own lifecycle state,
2. what it is waiting for (and who has to act),
3. all related artifacts together with their state.

The system must hold for humans working manually, for coding agents and their
subagents, and for the bots that already act in this repository.

### Success criteria

- A maintainer can answer "what is waiting for me?" with one label filter
  (`label:wait:maintainer`) and "what is blocked by what?" by opening any single
  artifact.
- No artifact is left in a lasting inconsistent state: after any edit the
  displayed block and the labels converge to the derived state within one
  workflow run.
- No pull request is merged while `oct-status` fails (required check, rollout
  step 4).
- Agents running with the committed hooks cannot drop the status block, forge
  fact labels or open a PR that violates the rules (tool-level prevention).
  Everything else is corrected server-side (heal + check).
- A new maintainer can learn the workflow from `docs/WORKFLOW.md` alone, using
  the real artifacts #537 / #573 / #574 as the walkthrough.
- After every action of the workflow, one recycled comment per artifact tells
  humans and agents what happened and which next steps and commands make sense.

### Non-goals

- Priorities and severities (`prio:*`, `priority: *`): untouched, unified later.
- Replacing the AI issue handler or the AI PR reviewer; they are integrated.
- Changing the Definition of Ready / Definition of Done; the system only
  reflects them.
- Per-view dynamic badges (Shields.io dynamic endpoints). Badges are static
  images rendered by the bot, so no external service is queried at view time.

## 2. Evidence from the repository (what the design must respect)

Collected on 2026-10-29 from git history (708 commits since 2026-01-27),
GitHub REST data (184 issues, ~577 PRs, 32 labels, branch protection) and all
workflows.

| # | Finding | Consequence |
|---|---|---|
| E1 | Dependabot opens 44 of the last 100 closed PRs. No spec, no template, labels from `dependabot.yml` mostly do not exist (`npm`, `workspace`, `python`, `backend`, `frontend`, `ci`; only `github_actions` exists, the config says `github-actions`); Dependabot comments about the missing labels on every PR (seen on #498). `reviewers: "user"` is a placeholder. | Dependency PRs get a lightweight profile; label sync fixes the Dependabot config. |
| E2 | Maintainer batch-merges Dependabot PRs (#457, #488) and the superseded PRs are closed unmerged. External PR #429 was closed in favour of the maintainer port #504 / #469. | New resolution `superseded` and edge `superseded-by`. |
| E3 | `formatter-bot` (CI job `autoformat`, token `RELEASE_TOKEN`) pushes `style: auto-format code [formatter-bot]` onto PR branches and `main`. `ci.yml` claims such pushes do not trigger runs, but the job uses a PAT. | Pushes by automation actors are never "author activity" and never cause strikes. |
| E4 | Sonar does not push. `sonarqubecloud[bot]` posts the check "SonarCloud Code Analysis" and a Quality Gate comment; the CI job "SonarCloud" only scans and is skipped for forks and Dependabot. Gitar (now part of Sonar) is installed as `gitar-bot[bot]`: it posts a check "Gitar", one dashboard comment that it edits in place (verdict, risk, options) and `COMMENTED` reviews (#576). Its dashboard on #560 reads "Auto-apply is off"; letting Gitar push is planned. Documented behaviour: fix commits (GPG-signed; author and message format not documented) go to the PR head branch, are never force-pushed and are only pushed after a green CI check of the fix; it stops after three consecutive Gitar commits or when someone else pushes. Auto-apply criteria (`.gitar/config/apply.md`, natural language, read from the default branch) limit fixes for review findings only; CI fixes and `gitar fix` ignore them, and path exclusions such as `.github/workflows/**` are not a documented setting while the GitHub App has write access to workflows. Merge blocking is a `REQUEST_CHANGES` review, not a check run. The open-source plan includes the Pro features auto-approve (`APPROVE` review, label `gitar-approved`), auto-merge and PR summary rewriting ("Enhance summaries", documented as an in-place block that preserves the text around it). `github-code-quality[bot]` posts reviews. `codecov-commenter` appears in the spotlight exclusion list. | Gates are an explicit configured list; missing or `skipped` checks are neutral. Gitar is both a findings source and a pushing actor (section 7). |
| E5 | About 30 check runs per PR. Branch protection requires only "Mojibake Check", no reviews, no conversation resolution, `enforce_admins` off. Squash only, branches deleted on merge, auto-merge allowed. The job "CI Summary" aggregates the core jobs. | `wait:ci` is derived from "CI Summary" plus the configured gate list, not from "all checks". Child PRs of a squash-merged parent are retargeted by GitHub, so only the current base counts. |
| E6 | The maintainer authors PRs (also via agents) under one login (`scheilch`) and GitHub forbids self-approval. Own PRs are approved by `oct-support` after an AI review (`pr-review.yml`, phase 2 job "Approve Check"). `oct-support` is an account of type `User`, not a bot. | Actor classes use a login allowlist, never the account type. |
| E7 | 32 labels with legacy vocabulary: `wip`, `blocked`, `accepted`, `needs-info`, `duplicate`, `wontfix`, `invalid`, `marked for closing`, `review` (no description), two priority schemes, two `community*` spellings. The issue handler adds `needs-triage`, which does not exist as a label. `spec` and `enhancement` are blue. | Rename in place (keeps assignments); recolor `spec` and `enhancement`. |
| E8 | Mixed artifacts: bug issues that are also specs (#365-#369), a tracking issue (#418), a manual test plan issue for a PR (#569, "[Test]: Manual test plan for PR #560"). | `spec` wins for the lifecycle; test-plan issues become the hardware-test mechanism (edge `verifies`). |
| E9 | Release automation (`github-actions[bot]`) pushes version bumps, CHANGELOG commits and tags straight to `main` and creates announcement discussions via GraphQL; a monthly workflow creates spotlight content and keeps its own bot exclusion list. | Profile `announcement`: no block, no strikes; the actor list is shared. |
| E10 | `CLAUDE.md`, DoR and DoD exist for four days (#555). Almost every artifact, including ~35 open specs, is older. | Backfill derives phases from facts; escalation only applies to artifacts created after activation. |
| E11 | Agent branches are named `claude/<random>`, contradicting the `type/description` rule in `CLAUDE.md`. Cloud sessions have REST access only (no GraphQL, no `gh`). | No state depends on branch names; hooks read through REST only. |
| E12 | `CLAUDE.md` forbids references to AI tools in commits, PR titles and descriptions. | The marker an agent hook leaves behind is neutral (`oct-src`), never "agent". |
| E13 | `.gitignore` ignored `docs/*` except an explicit whitelist, and also `.claude/`, `specs/`, `AGENTS.md` and `.github/agents/`. Specs live as GitHub issues (label `spec`), not as files. | Done in the first changes of this work: `docs/WORKFLOW.md` and `docs/superpowers/` are whitelisted (the `specs/` and `.specify/` rules moved above the `docs/*` block so the whitelist can win) and `.claude/` is tracked, with only `.claude/settings.local.json` and `.claude/worktrees/` staying local. Gitar also reads `.claude/rules/*` and `.claude/skills/` once they are tracked. |
| E14 | Commit identities leak the origin: commits on #560 / #570 are authored by `Claude` (login `claude`); commits on #555 by `Christian Scheil` resolve to the login `oct-support`. Gitar commits have not appeared yet and their message format is undocumented. | `oct-support` is also an identity behind human commits, so its allowlist entry applies to reviews, comments and labels only. The commit author may serve as a weak origin signal, never as a rule. Gitar commits must be checked against the "Validate Commit Messages" job before auto-apply is relied on. |
| E15 | The test suites under `scripts/` (`issue_handler`, `pr_reviewer`, `test_e2e_shard_distribution.py`) run in no CI job. Running them showed a time-dependent test (`test_budget_exceeded` fixes the month 2026-05 and fails since June), a never-matching pattern (`r"\\bhow\\b"` in `pattern_quality_scan.py`, used by the weekly `kb-growth` workflow), `issue_handler` at 76.7 % against its own gate of 80 % and `pr_reviewer` at 59 % for `main.py` without a gate. | One CI job runs all script suites together with the new package; the defects (month-dependent test, never-matching patterns, wrong thank-you scoring, 8 ruff findings) are fixed first and the coverage gates are set as decided (80 % for `issue_handler`, 57 % ratchet for `pr_reviewer`). |

## 3. Decisions taken in review

| Topic | Decision |
|---|---|
| Where the status lives | Bot-managed marker block at the top of the body (A), plus labels for filtering. For automation-authored artifacts the block is a pinned comment instead. |
| Strike counter | Per user, rolling 60 days, de-duplicated per (artifact, rule). |
| Maintainers | Escalation applies to maintainers as well. `/oct override` may be used by maintainers on themselves; it is logged. |
| Maintainer approval | An approval review by `oct-support` after its AI review counts as the maintainer approval for PRs authored by maintainers. `/oct approve` requests that AI review. PRs by other authors need an approval by a human with write access. Other bots (Gitar, code quality, Sonar) never approve. |
| Label migration | Rename in place as specified in section 9. |
| Blocker severity | Not graded. One orange for all `wait:*`. |
| Gitar | Auto-apply globally on, auto-approve on (an extra signal with the label `gitar-approved`, never a replacement for `oct-support`), auto-merge off. Findings source and pushing actor, see section 7. |
| Guide comment | One bot comment per artifact, edited in place after every workflow action, never a second one. It holds the last action, the next steps with ready-to-run commands, notices and escalation messages (section 5a). |
| Feature request | Stays open after its spec exists, mirrors the spec phase and closes with the spec (`resolution:superseded` if the spec is dropped). A feature never needs a separate feature issue. |
| Priority labels | Out of scope. |

## 4. Model

### 4.1 Artifact kinds and profiles

| Kind | Detected by | Lifecycle | Block |
|---|---|---|---|
| spec | label `spec` (wins over `bug` / `enhancement`) | spec lifecycle | full, in body |
| bug / support | label `bug` or `support`, no `spec` | bug lifecycle | full, in body |
| feature request | `enhancement`, no `spec` | bug lifecycle without `confirmed`; once a spec exists (edge `specified-by`) it stays open, mirrors the spec phase in its block and closes with the spec (`resolution:superseded` if the spec is dropped) | full, in body |
| tracking | title prefix `[Tracking]` | open until all children are closed; phase derived from children | full, in body |
| test plan | title prefix `[Test]` | `new` -> `in-progress` -> `done`; closing it clears `wait:hardware-test` on the target (edge `verifies`) | full, in body |
| pull request | PR | PR lifecycle | full, in body |
| dependency PR | PR by `dependabot[bot]` | PR lifecycle, no spec edge required | light, pinned comment |
| docs / chore PR | PR with `/oct no-spec <reason>`, or a Conventional Commit type in `docs`, `ci`, `chore`, `style`, `test` | PR lifecycle | full, spec edge optional |
| discussion | discussion | `open` -> `needs-spec` -> `specified` / `answered` / `closed` | full, in body |
| announcement | discussion or content created by an automation actor in the allowlist | none | none |

A spec issue is the work item of a feature from specification to completion. A
feature request is an optional input and never a prerequisite.

### 4.2 Axes

- `phase:*`: exactly one. Blue ramp: the darker, the further along.
- `wait:*`: zero or more. Orange only; severity is not graded. "No orange" means
  "nothing blocks".
- `resolution:*`: only on artifacts closed without a fix or merge. Grey.
- Type labels (`bug`, `spec`, `enhancement`, `support`, ...) keep their meaning.

Phases per kind:

| Kind | Phases |
|---|---|
| spec | `draft` -> `spec-review` <-> `spec-rework` -> `ready` -> `in-progress` -> `in-review` -> `verification` -> `done` |
| bug / feature request | `new` -> `triaged` -> `confirmed` (bugs only) -> `in-progress` -> `in-review` -> `verification` -> `done` |
| pull request | `draft` -> `in-review` -> `merged` / `closed` |
| discussion | `open` -> `needs-spec` -> `specified` / `answered` / `closed` |

A pull request in `in-review` without any `wait:*` label is mergeable.

Waits: `maintainer`, `findings`, `ci`, `prerequisite`, `hardware-test`,
`spec-fix`, `reporter`, `designer`.

Resolutions: `duplicate`, `wontfix`, `invalid`, `not-reproducible`,
`works-as-designed`, `superseded`, `abandoned`.

### 4.3 Who owns which label

- **Facts** are derived by the bot from GitHub state and re-applied if someone
  changes them by hand: `phase:new`, `draft` (PR), `in-progress` (open linked
  PR), `in-review`, `merged`, `done`, `closed`, `verification`, and the waits
  `maintainer`, `findings`, `ci`, `prerequisite`, `hardware-test` (while a
  linked test plan is open).
- **Declarations** are made by people through `/oct` commands (or the label,
  which the bot validates): `triaged`, `confirmed`, `spec-review`,
  `spec-rework`, `ready`, `wait:spec-fix`, `wait:reporter`, `wait:designer`,
  and every `resolution:*`.
- A declaration needs a reason where marked below. An invalid declaration is
  rejected with a comment and reverted.
- The bot owns only the namespaces `phase:`, `wait:` and `resolution:`. Foreign
  labels (`gitar-approved`, `gitar-managed`, `gitar-skip`, `dependencies`,
  `kb-scanned`, ...) are never touched.

### 4.4 Relations

Typed edges, always rendered in both directions.

| Edge | Inverse | Source (native first, prose fallback) |
|---|---|---|
| `implements` | `implemented-by` | closing reference; `Part of #n` / `Closes #n` |
| `stacked-on` | `stacked-by` | base branch of the PR equals the head branch of another PR (current base only) |
| `depends-on` | `blocks` | native issue dependencies; `Depends on #n` |
| `verifies` | `verified-by` | test-plan issue naming the target PR / spec |
| `specified-by` | `specifies` | feature request or discussion linked from a spec |
| `origin` | `spawned` | spec created from a discussion |
| `tracks` | `tracked-by` | sub-issues; task list in tracking issues |
| `superseded-by` | `supersedes` | body text, `/oct supersede #n` |
| `related` / `follow-up` | same | "Related issues" / "Follow-up to" sections |

References the parser cannot resolve unambiguously are listed as "unresolved"
in the block. The parser never guesses.

## 5. The status block

```
<!-- oct-status:v1 hash=<12 hex> -->
...rendered content...
<!-- /oct-status -->
```

- Content: badges for phase / waiting / counters, a "root blocker" line, an
  optional stack chain for PRs, an automation row (Gitar verdict, risk and auto-apply state, Sonar gate, `oct-support` review state) and the relations table (relation, artifact,
  phase, waiting on). Counters: `Parts n/m` for specs with parts, `DoD n/m` for
  the pull request template checklist.
- A "ball with" line names who has to act (maintainers, reporter, author,
  reviewer).
- Badges are static Shields.io images with the label text as alt text (screen
  readers and plain-text email clients stay informative).
- Rendering is deterministic; the hash covers the rendered content. A write is
  skipped when the hash is unchanged.
- Placement: top of the body. For artifacts authored by an automation actor
  whose body is regenerated (Dependabot) the block lives in one pinned comment
  marked `<!-- oct-next:v1 -->` (the single guide comment marker; the earlier
  `<!-- oct-status:comment -->` is superseded).
- Size: the relations table is capped at 25 rows; the rest is summarized as
  "and n more".

### Protection against overwriting

The body is a projection of the state, never the state itself. A lost block
costs display only.

1. Agent hook: every write with a `body` has the current block spliced in (see
   section 8).
2. Heal: the workflow reacts to `edited` and restores the block. Edits by the bot
   itself and edits that leave the hash unchanged are ignored.
3. Required check `oct-status` is red while the block of a PR is missing or stale.
4. Daily audit finds and heals drift on all open artifacts.

GitHub cannot forbid body edits server-side. Humans in the web UI are protected
by 2-4 and see the block restored within seconds.

## 5a. The guide comment

Each artifact gets exactly one bot comment, marked `<!-- oct-next:v1 -->`. It is
created on the first workflow action and edited in place after every later one;
the bot never posts a second comment. For Dependabot PRs and other
automation-authored artifacts this comment also carries the status block.

Sections:

1. Last action: what the workflow just did and why (for example "set
   `wait:maintainer`: no approval on head 5f26740"), or the error of a rejected
   command.
2. You are here: phase and waits in one line, with the link to the matching
   anchor in `docs/WORKFLOW.md`.
3. Next steps: at most five entries, ordered by priority, each with the actor
   (maintainer, author, reporter, reviewer, anyone) and a ready-to-run command in
   a code block. Steps that wait on something else are listed as notes without
   a command.
4. Commands valid now: only the commands that are legal in the current state,
   with their arguments. Invalid ones are omitted.
5. Notices: violations and escalation messages (section 10) with the rule
   anchor; resolved ones collapse into a `<details>` block.
6. History: the last five actions in a `<details>` block.
7. A machine-readable block `<!-- oct-next-data {...} -->` with phase, waits and
   the next steps as JSON. Hooks and agents read it; the SessionStart hook
   injects it into the session.

Next steps come from the state machine in `rules.py`: the legal transitions from
the current phase plus the action that clears each wait (`wait:maintainer`:
`/oct approve`; `wait:findings`: the open threads with links;
`wait:hardware-test`: `/oct verified <device>` or the open test plan;
`wait:prerequisite`: the blocking artifacts). When a precondition is not met,
the precondition is shown instead of the command, for example the unticked DoR
items before `/oct ready`.

Recycling: the bot finds the comment by marker and author, updates it with
`PATCH` and writes only when the rendered content changed. Duplicates caused by
races are resolved by keeping the oldest and deleting the rest. If someone
deletes the comment, the next action recreates it; deleting is not a violation.
The comment stays well below the GitHub size limit; history and resolved
notices are truncated first.

Notifications: edits do not notify, and this is accepted. There is never a second
comment, also not when the ball changes hands. As a best effort the bot mentions
the person who has the ball only in the edit where it changes; whether GitHub
notifies on a newly added mention in an edited comment is observed in shadow
mode and has no fallback. People find their work through the `wait:*` label
filters, not through notifications.

Reactions on the command comment (eyes, thumbs up, thumbs down) stay. The
explanation of a rejection goes into section 1 of the guide comment, never into
a new comment. The comment never starts with `gitar` and never mentions
`@gitar-bot`.

## 6. Derivation of facts

The pure function `derive(facts, declarations) -> (phase, waits, resolution)`
lives in `rules.py`; this table is its specification.

| Result | Rule |
|---|---|
| `wait:maintainer` | PR is not a draft, and (author is a maintainer: no approving review by `oct-support` on the current head; any other author: no approving review by a human with write access on the current head). Approvals by other bots, including Gitar's `APPROVE` review and its label `gitar-approved`, never count. A push that changes code invalidates the approval: pushes by humans, agents and `gitar-bot[bot]` do, pushes by `formatter-bot` do not (per actor flag `invalidates_approval` in `config.yml`). |
| `wait:findings` | Unresolved review threads from any reviewer, a `REQUEST_CHANGES` review by `gitar-bot[bot]` (until `gitar unblock` or a new green review), a failed Sonar Quality Gate, or a negative Gitar verdict in its dashboard comment. |
| `wait:ci` | "CI Summary" or any other check in the configured gate list is pending or failed. Checks that are absent or `skipped` are neutral (Dependabot / forks skip Sonar). Quality-gate failures belong to `findings`, not `ci`. |
| `wait:prerequisite` | An `implements` target is not at `ready` or later; or a `depends-on` target or a `stacked-on` parent is open and not merged. Merged parents drop out of the chain. |
| `wait:hardware-test` | A linked `verifies` test plan is open, or the spec declares hardware verification and has no `/oct verified`. Merging does not clear it. |
| `phase:in-progress` | An open linked PR is a draft, or the legacy `wip` label was set (migrated). |
| `phase:in-review` | An open linked PR is ready for review. |
| `phase:verification` | All parts are merged and `wait:hardware-test` is set. |
| `phase:done` | Merged / closed as completed and no `wait:hardware-test`. |
| `phase:closed` | Closed without a fix; requires a `resolution:*`. The bot asks for one when it is missing. |

Bots' own comments, reviews and pushes (allowlist, section 7) are never treated
as author activity; they only feed `findings` and `ci` through checks.

## 7. Actors

Actor classes come from a login allowlist in `scripts/oct_status/config.yml`,
shared with `monthly-community-spotlight.yml` (not from the account type, see E6).

| Actor | Class | Behaviour |
|---|---|---|
| maintainer(s), contributors | human | full escalation (section 10) |
| first-time fork contributors | human | hints only, never blocked, tone as the existing "Welcome & Guide" |
| `dependabot[bot]` | automation | dependency PR profile, block as pinned comment, label config repaired |
| `formatter-bot` | automation, pushes | pushes ignored for activity and strikes; they do not invalidate approvals |
| `github-actions[bot]` | automation | releases, version bumps, announcements: profile `announcement` |
| `oct-support` | automation (type User) | AI reviewer / issue handler; its approval is the maintainer approval for maintainer-authored PRs |
| `gitar-bot[bot]` | automation, pushes | review findings, dashboard comment and optional fix commits on the PR head branch (these invalidate approvals); foreign labels `gitar-*` are left alone; its approval is never the maintainer approval |
| `sonarqubecloud[bot]`, `github-code-quality[bot]`, `codecov-commenter` | automation | feed `findings` / `ci`, never approve, never counted as activity |
| coding agents | human login + marker | covered by hooks; the marker `<!-- oct-src:1 -->` lets the server tell the origin apart for messages, not for security |

Gitar executes commands from comments that start with `gitar` or `@gitar` or that mention `@gitar-bot`. Comments written by the status bot never start with those strings and never mention the bot.

### Gitar as a pushing actor

1. A push by `gitar-bot[bot]` invalidates an existing approval. `oct-support`
   has to approve the new head, so `wait:maintainer` returns until it does.
2. Gitar pushes never change `phase`, never count as author activity and never
   cause strikes. They re-trigger `wait:ci` and `wait:findings` like any push.
3. Protected paths: Gitar's CI fixes ignore the apply criteria, path exclusions
   are not a documented Gitar setting and its GitHub App can write workflows. A
   push by any automation actor that touches a path from `protected_paths` in
   `config.yml` (initially `.github/workflows/**`, `scripts/oct_status/**`,
   `.gitar/**`, `.claude/**`, `.gitignore`) sets `wait:findings` and posts a
   comment naming the files. `oct-status` fails until a maintainer acknowledges
   with `/oct accept-paths`. The acknowledgement covers only the head recorded when
   the notice listed the files. The rule applies to any automation actor,
   Dependabot and `formatter-bot` included, so their pushes to workflow files
   also need the acknowledgement.
4. `.gitar/config/apply.md` (natural language, read from the default branch, so
   a PR cannot loosen it) restricts auto-applied fixes for review findings to
   low-risk categories and excludes security-relevant code. CI fixes are covered
   by rule 3.
5. Gitar never pushes to `main`. Pushes to fork PRs are not documented and are
   treated as unavailable. Dependabot PRs stay skipped (Gitar default).
6. If `formatter-bot` pushes after Gitar, Gitar stops (documented: it stops when
   someone else pushes); the status system neither amplifies nor hides this, the
   block just shows the current checks.
7. Stack drift: a Gitar push to the head branch of a PR moves the base of every
   PR stacked on it. The chain in the block marks such a child as "parent
   moved" (a notice, no label); rebasing or merging the parent branch stays a
   manual or agent step.

## 8. Enforcement for agents and subagents

Layer 1 - tool level, committed `.claude/settings.json`:

- Body guard (PreToolUse on all body-writing GitHub tools and on `gh issue|pr`
  and direct API calls through Bash): splices the current block into the new body
  (`updatedInput`). If the block cannot be read (offline, no token) the write is
  denied and the agent is told to use a comment instead. Fail closed.
- Fact-label guard: setting or removing a fact label is denied with the `/oct`
  alternative in the message.
- PR creation gate: denied unless the body contains `Closes #n` / `Part of #n`
  (or `/oct no-spec <reason>` for exempt kinds), the template sections of
  `.github/pull_request_template.md` are present and no item was deleted, and the
  linked spec is at `phase:ready` or later with no open `wait:prerequisite`, unless
  the PR is declared `stacked-on` its prerequisite.
- SessionStart context: the block and the guide comment data of the artifact the session works on (from
  the task text or the branch's PR) and the key rules.
- Body and comment writes by hooked sessions append the marker `<!-- oct-src:1 -->`.
- Denial messages quote the valid next steps and commands from the guide comment data, so an agent can correct itself in one step.
- All reads use REST only (E11).

Layer 2 - server level (covers hook-less runtimes and the web UI): heal, fact
reversion, required check `oct-status`, escalation for humans.

Layer 2b - Gitar. Gitar reads `CLAUDE.md`, `AGENTS.md` and `.gitar/` from the repository. A rule file `.gitar/rules/oct-status.md` tells it to leave the `oct-status` block and the `phase:` / `wait:` / `resolution:` labels alone and to write Conventional Commit messages; `.gitar/config/apply.md` limits auto-applied finding fixes (section 7). Decided settings: auto-apply on globally, auto-approve on as an additional signal, auto-merge off (it would bypass `wait:maintainer`). A Gitar `APPROVE` would also satisfy a future required-review branch rule, so such a rule must name `oct-support` or code owners explicitly. "Enhance summaries" stays off until shadow mode proves that Gitar's in-place summary block leaves the status block and its HTML comment markers intact.

Layer 3 - `CLAUDE.md` gets a short section pointing to `docs/WORKFLOW.md`.

Hooks intercept tool calls, not prompts, so they must apply to subagents as
well. This is verified by a test in the plan before it is claimed (section 14).

## 9. Labels and migration

| Existing | Becomes | Note |
|---|---|---|
| `wip` | `phase:in-progress` | rename |
| `needs-info` | `wait:reporter` | rename; issue handler updated |
| `blocked` | `wait:prerequisite` | rename |
| `accepted` | `phase:triaged` | rename |
| `duplicate`, `wontfix`, `invalid` | `resolution:duplicate`, `resolution:wontfix`, `resolution:invalid` | rename |
| `needs-triage` (not existing) | `phase:new` | issue handler fixed |
| `spec` | `spec` | recolor violet |
| `enhancement` | `enhancement` | recolor light green |
| `review`, `marked for closing`, `solution`, `kb-scanned`, `prio:*`, `priority: *`, `community*`, `FAQ`, `question`, `user-report`, `help wanted`, `ux`, `wizard`, `documentation`, `dependencies`, `github_actions` | unchanged | `review` is undocumented: ask before touching |

New labels are created from `scripts/oct_status/labels.yml` by an idempotent
sync. Colors:

- `phase`: `new`/`draft` #cfe0fa, `triaged`/`spec-review`/`spec-rework` #a8c5f3,
  `confirmed` #7ba3ec, `ready` #5b8ee6, `in-progress` #3a73d8, `in-review` #2a5cc0,
  `verification` #1e4590, `done`/`merged` #1a7f37, `closed` #6e7781.
- `wait:*` #f2a33a. `resolution:*` #c9d1d9.

The sync also creates the labels Dependabot expects or corrects
`dependabot.yml`, and fixes its `reviewers` placeholder.

## 10. Escalation for humans

A violation is a breach of a rule from the catalogue; a notice is advice
without a strike.

Catalogue (initial; each rule has an anchor in `docs/WORKFLOW.md`):

| ID | Violation |
|---|---|
| V01 | PR without an `implements` edge and no `/oct no-spec` |
| V02 | Fact label set or removed by hand |
| V03 | Status block removed or edited by hand |
| V04 | PR marked ready while a prerequisite is neither merged nor declared as its stack parent |
| V05 | Template section or DoR / DoD item deleted |
| V06 | PR for a spec that is not `ready` |
| V07 | Invalid declaration (for example `/oct ready` without a complete DoR checklist) |
| V08 | Closing a `verification` artifact without `/oct verified` |

Ladder, counted per user over 60 days, de-duplicated per (artifact, rule):

1. **First violation:** a notice in the guide comment (section 5a, never a new comment) containing what
   happened, what was expected, the next steps as ready-to-run `/oct` commands
   and the link to the anchor in `docs/WORKFLOW.md`. Check stays green.
2. **Second violation:** the same, plus the hint that a maintainer can override
   with `/oct override <reason>`.
3. **Third and later:** the check `oct-status` fails on the affected pull
   request until the issue is fixed or overridden. Issues and discussions cannot
   be blocked; the bot reverts the offending change and says so.

Rules for fairness: automation actors and first-time fork contributors are
exempt from strikes; an overridden violation is not counted; each strike
expires 60 days after it was recorded (rolling window per strike). Every violation and override is appended to a
locked ledger issue ("oct-status ledger", created by the label sync) so the
counter is auditable and does not rely on search.

Maintainers are subject to the same ladder and may override on themselves.

## 11. Commands

| Command | Who | Effect |
|---|---|---|
| `/oct review` | spec author | `spec-review` after a complete DoR checklist |
| `/oct rework <reason>` | reviewer | `spec-rework` + `wait:spec-fix` |
| `/oct ready --reviewer <login or "independent-review">` | reviewer | `ready`; DoR checklist complete; reviewer differs from the author unless "independent-review" |
| `/oct triage`, `/oct confirm` | maintainer | `triaged`, `confirmed` |
| `/oct approve` | author / maintainer | requests the AI review by `oct-support`; its approval clears `wait:maintainer` |
| `/oct verified <device or note>` | maintainer | clears `wait:hardware-test` |
| `/oct needs-hardware-test`, `/oct needs-info`, `/oct designer <reason>` | maintainer | sets the wait |
| `/oct no-spec <reason>` | PR author | exempts a PR from V01 |
| `/oct supersede #n` | maintainer | edge + `resolution:superseded` |
| `/oct override <reason>` | maintainer | clears a block, logged |
| `/oct accept-paths` | maintainer | acknowledges a push by automation to protected paths, logged in the guide data and the run summary |

Commands are accepted only from users with write access, answered with a
reaction and, on error, an entry in the guide comment (section 5a).

## 12. Components and workflows

`scripts/oct_status/` (Python, `httpx`, own `pyproject.toml` and tests, same
layout as `scripts/issue_handler/`):

| Module | Role |
|---|---|
| `facts.py` | REST (and GraphQL inside Actions) facts: closing refs, reviews, threads, check runs, base / head, sub-issues, dependencies |
| `graph.py` | edges and inverses, prose parser, unresolved list |
| `rules.py` | `derive`, state machines per kind, validation of declarations |
| `render.py` | block rendering and hashing |
| `apply.py` | label diff, block splice or pinned comment, guide comment upsert, loop guards |
| `commands.py` | `/oct` parser and authorization |
| `guide.py` | next-step selection and guide comment rendering (section 5a) |
| `ledger.py` | strike counting and ledger writes |
| `hooks/` | PreToolUse / SessionStart scripts for section 8 |
| `main.py` | `--event`, `--check`, `--audit`, `--backfill`, `--dry-run` |

`.github/workflows/oct-status.yml`:

- Triggers: `issues`, `pull_request_target` (never checks out PR code),
  `pull_request_review`, `pull_request_review_thread`, `check_suite` /
  `workflow_run` (CI done), `issue_comment` (commands), `discussion`,
  `discussion_comment`, a daily audit and `workflow_dispatch`. The audit is
  scheduled off the full hour. Implementation note: `pull_request_review_thread`
  is a webhook-only event that GitHub Actions cannot trigger on, so a resolved
  thread is picked up by the next event of the pull request or the audit.
- One concurrency group per artifact. Fan-out after a change is limited to the
  connected component of `stacked-on` / `depends-on` edges, at most 25 nodes;
  hash equality ends cascades.
- Writes use `BOT_PAT`; reads use `GITHUB_TOKEN`. Dependabot runs get base
  repository secrets through `pull_request_target`.
- Existing workflows: `issue-handler.yml` skips events whose sender is the status
  bot; its classification labels are translated (E7); `pr-review.yml` stays the
  AI reviewer and gains the `/oct approve` entry point; the automation allowlist
  is shared with the spotlight workflow.

## 13. Documentation

`docs/WORKFLOW.md` (English) is part of the Definition of Done of this system:

1. Lifecycle diagrams (Mermaid) per kind.
2. Reference tables for `phase`, `wait`, `resolution`: meaning, owner (bot or
   human), how to resolve.
3. Command reference.
4. "You are up when..." with ready-made filter links and an onboarding checklist
   for new maintainers.
5. A dated walkthrough of #537 -> #573 / #574 (stacked on #560 -> #570 -> #571
   -> #572), the bug #575 and a Dependabot PR, with the block, the guide
   comment and the label set at each step.
6. One anchor per rule V01-V08 with a wrong and a right example.
7. Troubleshooting (block missing, label reset, `oct-status` red).

The walkthrough snippets are rendered from frozen fixtures
(`scripts/oct_status/tests/fixtures/`); a CI test compares them with the
renderer output, so the documentation cannot drift. `CONTRIBUTING.md`,
`CLAUDE.md`, the issue forms and the pull request template link to it.

## 14. Tests and rollout

### Tests (deterministic, no real GitHub, coverage >= 80 %)

- The existing suites under `scripts/` run in the same CI job as the new package (E15).
- Table-driven tests for `derive` and every illegal transition.
- Golden tests for renderer and documentation snippets (#537, #560, #573, #574,
  #575, #577, a Dependabot PR).
- Golden tests for the guide comment per state (state -> next steps and valid commands), recycling (create, update, duplicate cleanup, deleted comment) and the size cap.
- Hook tests: PreToolUse JSON in, `updatedInput` or denial out; a test that
  proves hooks also fire for subagents (blocking for the claim in section 8).
- Parser tests for prose edges; ledger / strike tests; `actionlint` for the workflow.
- Actor-profile tests: a Gitar push invalidates an approval, a formatter-bot push does not; foreign labels stay untouched; no outgoing comment starts with a Gitar trigger; the protected-path guard fires for automation pushes and not for human pushes.

### Rollout (one spec issue and PR per step)

0. Label sync (`labels.yml`), renames, recolors, ledger issue, Dependabot
   config repair.
1. Shadow mode: everything is computed for all open artifacts and written only to
   the job summary; compared with reality for a week.
2. Write mode for new events plus a rate-limited backfill. Phases are derived
   from facts; no strikes for existing artifacts.
3. Hooks, `.claude/settings.json`, `docs/WORKFLOW.md`, `CLAUDE.md` (the
   `.gitignore` changes are already in place).
4. Enforcement: `oct-status` becomes a required check (maintainer action in the
   repository settings), strikes start.

Rollback: disable the workflow and remove the required check; labels and blocks
stay inert.

## 15. Open points and assumptions to verify in the plan

Rulings made during implementation (deviations from the text above):

- Write mode is gated by the repository variable `OCT_STATUS_WRITE` (maintainer go/no-go after the shadow week); strikes stay inactive until `strikes_enabled_from` is set, and that must not happen before the backfill.
- The merge gate is the commit status context `oct-status` on the PR head (posted only in write mode), not a check run: checks of `pull_request_target` runs attach to the base commit.
- V05 is not reverted automatically (the notice persists until the template is restored); V08 is reverted by reopening the issue at level 3 (built: `main._reopen`; the notice then resolves only on `/oct verified` or an override).
- An open spec whose parts are all merged stays in progress; the automation row has no Gitar risk or auto-apply state until dashboard parsing exists.
- `/oct supersede` is accepted only on closed artifacts; the `superseded-by` edge is not written yet.
- GitHub keeps one pending run per concurrency group, so a queued command comment can be dropped: repeat a command that shows no reaction.

- Hooks apply to subagents and `updatedInput` is honoured: **verified** on 2026-10-30 (Windows, Claude Code latest). A PreToolUse hook on `Bash` rewrote `echo original` to `echo rewritten` (`updatedInput` honoured), and the hook fired for a subagent's Bash call (log entry carries an `agent_id`; the subagent's output was rewritten as well). Consequences: the guard may splice bodies through `updatedInput`, and hooks are a real prevention for subagents. A crashing hook is a non-blocking error (the tool call proceeds), so the guard must exit with code 2 on any internal error. Hooks must be portable to Windows (`python`, no `/tmp`).
- Bot identity: `issue-handler.yml` mentions `scheilch`, `rules.yml` mentions
  `oct-support`; confirm which account the `BOT_PAT` belongs to.
- Gitar / approval experiment (MA-8, throwaway PR #586, 2026-10-30), results:
  - Status block: a hand-written block at the top of the description survived Gitar's summary update unchanged; Gitar appends its own `----` + `## Summary by Gitar` section at the end of the description (so Gitar edits the description at arbitrary times: description writes must re-read before patching).
  - Gitar's commit (after `gitar fix this` in a review thread): author and committer name `Gitar`, email `noreply@gitar.ai`, commit-API login `gitar-bot` (a User account; reviews and comments come from `gitar-bot[bot]`), conventional subject, trailer `Co-authored-by:` naming the human who triggered it. "Validate Commit Messages" passed.
  - `formatter-bot` commits have no GitHub login (author and committer `null`), git name `formatter-bot`, email `noreply@opencloudtouch.org`; they passed commit validation. Gitar did not loop after formatter-bot pushes (it answered "No push was confirmed in this run" when formatter-bot had fixed the finding first).
  - The maintainer's own local commits carry the login `oct-support` (author and committer; the git identity is linked to that account). `oct-support` therefore appears as a push author for human work.
  - `oct-support` review: APPROVED on one head, later shown as DISMISSED after further pushes; `Approve Check` ran green on the later pushes but did NOT re-approve (it returns early when `oct-support` has no review threads). A renewed approval needs a new review request (`/oct approve`).
  - Gitar's own comment on the PR reported "Auto-apply is off" and "Auto-approval: Not enabled", i.e. the dashboard does not have the decided settings active (MA-4 to re-check).
  - Consequences for the implementation (Round C): add `gitar-bot` (commit login) as a pushing automation actor; `oct-support` must not count as a push-automation actor (its commits are the maintainer's); only automation entries with `pushes: true` count for the protected-path guard.
- Gitar: auto-apply (global), auto-approve and auto-merge are decided; confirm "Enhance summaries" and "Skip drafts" in the dashboard. On a throwaway PR verify the author and message of a `gitar fix this` commit against "Validate Commit Messages", that the status block survives a summary update, that `oct-support` re-reviews after a Gitar push, and what happens when `formatter-bot` pushes afterwards (the documentation says both "stops when someone else pushes" and "one or two consecutive commits").
- Merge-gate mode of `oct-status`: fail only on strikes and stale blocks (default), or also while any `wait:*` label is set on a ready PR. The second mode makes the check the single go / no-go and also holds back native auto-merge (GitHub's or Gitar's) until `wait:maintainer` is cleared. Decide with rollout step 4.
- `oct-support` appears as the login behind human commits (#555); confirm what that account is.
- Dependabot rewriting PR descriptions on rebase (assumed; shadow mode verifies).
- Writing to discussions through GraphQL from Actions, and the behaviour of
  discussion labels.
- Adding the required check is a repository setting only an admin can change.
  `enforce_admins` is off today, so an admin merge can still bypass it; decide
  whether to switch it on together with rollout step 4.
- The undocumented label `review`.

## 16. Definition of Ready / Done mapping

Backend / frontend / OpenAPI / i18n / migrations: n/a (no application code).
Applicable: tests (above), documentation (section 13), CI (new workflow plus
`actionlint`), security (`pull_request_target` never executes PR code; no tokens
in logs; ledger holds logins only), hardware verification: n/a. The
implementation is split along section 14 into separate spec issues, each with
its own Definition of Ready.
