"""Command line entry point of the OCT status system.

Modes: ``--labels`` (label sync), ``--event/--payload`` (one webhook event), ``--check`` (is the block of
the event's artifact current, and is nothing blocking it?), ``--audit`` (heal drift on every open
artifact) and ``--backfill`` (rate-limited, resumable migration of the open artifacts, MA-6).

Untrusted data rules: event payloads are only ever parsed as JSON and used as numbers or strictly
validated tokens; text from artifacts is written to the job summary (Markdown) and never to stdout,
where a ``::command::`` line would be interpreted by the runner.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from oct_status import commands
from oct_status import notices as persisted
from oct_status.api import GitHubApi
from oct_status.apply import _comments, _find_guides, apply_state, desired_labels, guides_in, is_own_event
from oct_status.config import Config, load_config
from oct_status.facts import fetch_snapshot
from oct_status.graph import PROPAGATING, build_graph, parse_prose_edges, walk_component
from oct_status.guide import next_steps, protected_notice, render_guide
from oct_status.labels_sync import LedgerIssueError, ensure_ledger_issue, sync_labels
from oct_status.ledger import Ledger, LedgerError, strikes_active
from oct_status.model import Derived, Edge, Graph, Phase, Snapshot
from oct_status.notices import Acceptance, GuideState, Record
from oct_status.render import extract_block, render_block, splice_block
from oct_status.rules import derive, protected_changes
from oct_status.violations import EventFacts, Violation, classify_actor, detect, escalate

LABELS_SPEC = Path(__file__).resolve().parent / "labels.yml"
CONFIG_PATH = Path(__file__).resolve().parent / "config.yml"

EXIT_OK = 0
EXIT_API_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_STALE = 1
DEFAULT_BACKFILL_STATE = "oct-backfill-state.json"

_PER_PAGE = 100
_MAX_PAGES = 50
_SHA = re.compile(r"[0-9a-f]{40}")
_ISSUE_EVENTS = {"issues", "issue_comment"}
_PR_EVENTS = {"pull_request", "pull_request_target", "pull_request_review", "pull_request_review_comment"}
_DISCUSSION_EVENTS = {"discussion", "discussion_comment"}


class ConfigError(Exception):
    """Required configuration is missing."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oct_status", description="OpenCloudTouch status system")
    parser.add_argument("--labels", action="store_true", help="synchronise labels and the ledger issue")
    parser.add_argument("--event", help="webhook event name to process (needs --payload)")
    parser.add_argument("--payload", help="path of the event payload JSON (untrusted data)")
    parser.add_argument("--check", action="store_true", help="exit 1 when the block of the event's artifact is stale")
    parser.add_argument("--audit", action="store_true", help="heal drift on all open artifacts")
    parser.add_argument("--backfill", action="store_true", help="migrate the open artifacts in rate-limited batches")
    parser.add_argument("--limit", type=int, default=25, help="artifacts per backfill run (default 25)")
    parser.add_argument("--state", help="backfill state file (default: $OCT_BACKFILL_STATE or oct-backfill-state.json)")
    parser.add_argument("--dry-run", action="store_true", help="plan only, perform no writes")
    return parser


def _credentials() -> tuple[str, str]:
    # BOT_PAT is preferred when present: the writing jobs (status-write, labels, backfill) get it; the
    # shadow-mode `status` job and the check get GITHUB_TOKEN only.
    token = os.environ.get("BOT_PAT") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ConfigError("missing credentials: set BOT_PAT (preferred) or GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        raise ConfigError("missing or invalid GITHUB_REPOSITORY (expected owner/repo)")
    return token, repo


def _emit(lines: list[str]) -> None:
    for line in lines:
        print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and lines:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("".join(f"- {line}\n" for line in lines))


async def _run_labels(api: GitHubApi, dry_run: bool, cfg: Config | None = None) -> list[str]:
    cfg = cfg or load_config(CONFIG_PATH)
    ops = await sync_labels(api, LABELS_SPEC, dry_run=dry_run)
    try:
        ledger = await ensure_ledger_issue(api, dry_run=dry_run, bot_logins=cfg.bot_logins, configured=cfg.ledger_issue)
    except LedgerIssueError as exc:
        raise ConfigError(str(exc)) from exc
    prefix = "[dry-run] " if dry_run else ""
    return [*ops, f"{prefix}ledger issue: {'would be created' if ledger == 0 else f'#{ledger}'}"]


# --- event pipeline -------------------------------------------------------------------------------


def _number(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    node: Any = payload
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


async def resolve_artifact(api: GitHubApi, event_name: str, payload: dict[str, Any]) -> int | None:
    """Number of the issue, pull request or discussion an event is about (``None`` if none)."""
    if event_name in _ISSUE_EVENTS:
        return _number(_nested(payload, "issue", "number"))
    if event_name in _PR_EVENTS:
        return _number(_nested(payload, "pull_request", "number"))
    if event_name in _DISCUSSION_EVENTS:
        return _number(_nested(payload, "discussion", "number"))
    if event_name == "check_suite":
        for pull in _nested(payload, "check_suite", "pull_requests") or []:
            if (number := _number(_nested(pull, "number") if isinstance(pull, dict) else None)) is not None:
                return number
        sha = _nested(payload, "check_suite", "head_sha")
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):  # untrusted: never build a path from it
            return None
        resp = await api.request("GET", f"/commits/{sha}/pulls")
        resp.raise_for_status()
        for pull in resp.json():
            if (number := _number(pull.get("number"))) is not None:
                return number
    return None


class Workspace:
    """Lazily loaded snapshots of one run, and the graph and derived state over them."""

    def __init__(self, api: GitHubApi, cfg: Config) -> None:
        self.api = api
        self.cfg = cfg
        self._snaps: dict[int, Snapshot | None] = {}
        self.warnings: list[str] = []
        self._open_prs: list[dict[str, Any]] | None = None
        self._open_items: list[dict[str, Any]] | None = None
        self._referrers: dict[int, set[int]] | None = None
        # Persisted guide state per loaded artifact; ``None`` when its comments could not be read.
        self.states: dict[int, GuideState | None] = {}
        self.acceptances: dict[int, Acceptance] = {}  # `/oct accept-paths` accepted in this run

    async def open_items(self) -> list[dict[str, Any]]:
        """All open issues and pull requests, bodies included (one paged listing)."""
        if self._open_items is None:
            self._open_items = await _paged(self.api, "/issues", {"state": "open"}, self.warnings)
        return self._open_items

    async def referrers(self, number: int) -> set[int]:
        """Open artifacts whose body names `number` in a Closes / Part of / Depends on phrase.

        Needed for the reverse direction, which no REST endpoint lists.
        """
        if self._referrers is None:
            index: dict[int, set[int]] = {}
            for item in await self.open_items():
                source = int(item["number"])
                for edge in parse_prose_edges(source, item.get("body") or "")[0]:
                    index.setdefault(edge.target, set()).add(source)
            self._referrers = index
        return self._referrers.get(number, set())

    async def open_prs(self) -> list[dict[str, Any]]:
        if self._open_prs is None:
            self._open_prs = await _paged(self.api, "/pulls", {"state": "open"}, self.warnings)
        return self._open_prs

    async def load(self, number: int) -> Snapshot | None:
        if number not in self._snaps:
            heads = frozenset(p["head"]["ref"] for p in await self.open_prs())
            try:
                snap = await fetch_snapshot(self.api, number, open_pr_heads=heads, cfg=self.cfg)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                self._snaps[number] = None  # dangling reference
            else:
                if snap.timeline_unknown:
                    self.warnings.append(
                        f"WARNING: label history of #{number} unreadable; fact labels are not trusted for its phase"
                    )
                self._snaps[number] = await self._with_comments(snap)
        return self._snaps[number]

    async def _with_comments(self, snap: Snapshot) -> Snapshot:
        """Read the comments once: the persisted guide state and, for a PR, the author's `/oct no-spec`."""
        try:
            comments = await _comments(self.api, snap.number)
        except httpx.HTTPError:
            self.states[snap.number] = None  # fail closed: the guide is not rewritten from nothing
            self.warnings.append(
                f"WARNING: comments of #{snap.number} unreadable; its guide comment is not rewritten "
                "and a /oct no-spec waiver is not seen"
            )
            return snap
        guides = guides_in(comments, self.cfg.bot_logins)
        state = persisted.parse_state(guides[0].get("body") or "") if guides else GuideState()
        self.states[snap.number] = state
        if state is None:
            self.warnings.append(
                f"WARNING: guide data of #{snap.number} is missing, oversized or invalid; the guide comment is "
                "not rewritten (delete it to start over)"
            )
        reason = await commands.find_no_spec(self.api, snap, comments) if snap.is_pr else None
        return replace(
            snap,
            no_spec_reason=reason or snap.no_spec_reason,
            paths_accepted=state.accepted.sha if state and state.accepted else snap.paths_accepted,
            paths_pending=state.pending if state else "",
        )

    def patch(
        self,
        number: int,
        add: list[str],
        remove: list[str],
        no_spec_reason: str | None = None,
        paths_accepted: str | None = None,
    ) -> None:
        """Reflect a command's effect in the loaded snapshot (the labels were written, or are planned)."""
        snap = self._snaps.get(number)
        if snap is None:
            return
        labels = (snap.labels - set(remove)) | set(add)
        self._snaps[number] = replace(
            snap,
            labels=frozenset(labels),
            no_spec_reason=no_spec_reason or snap.no_spec_reason,
            paths_accepted=paths_accepted or snap.paths_accepted,
        )

    async def neighbors(self, number: int) -> list[Edge]:
        """Edges of `number` whose other end exists; loads the neighbours (and stack partners)."""
        snap = await self.load(number)
        if snap is None:
            return []
        if snap.is_pr:
            for pull in await self.open_prs():
                if pull["number"] != number and (
                    pull["head"]["ref"] == snap.base_ref or pull["base"]["ref"] == snap.head_ref
                ):
                    await self.load(pull["number"])
        for source in sorted(await self.referrers(number)):
            await self.load(source)
        edges = self.graph(derive_all=False).edges_of(number)
        return [e for e in edges if await self.load(e.target) is not None]

    async def fan_out(self, number: int) -> list[Edge]:
        """The neighbours a change of `number` propagates to (all neighbours are still loaded)."""
        return [e for e in await self.neighbors(number) if e.type in PROPAGATING]

    def graph(self, derive_all: bool = True) -> Graph:
        graph = build_graph({n: s for n, s in self._snaps.items() if s is not None})
        if derive_all:
            for number, snap in graph.snapshots.items():
                if (derived := derive(snap, graph, self.cfg)) is not None:
                    graph.derived[number] = derived
        return graph


async def _paged(
    api: GitHubApi, path: str, params: dict[str, Any], warnings: list[str] | None = None
) -> list[dict[str, Any]]:
    """All pages of a listing; when the page cap is hit the result is incomplete and `warnings` says so."""
    items: list[dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        resp = await api.request("GET", path, params={**params, "per_page": _PER_PAGE, "page": page})
        resp.raise_for_status()
        batch = resp.json()
        items += batch
        if len(batch) < _PER_PAGE:
            break
    else:
        if warnings is not None:
            warnings.append(f"WARNING: listing {path} was cut off after {_MAX_PAGES} pages; results are incomplete")
    return items


@dataclass
class Outcome:
    number: int
    derived: Derived | None
    block: str | None = None
    writes: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    # Problems of the `oct-status` gate after this run (open PRs only; ``None`` for other artifacts).
    gate: list[str] | None = None
    head_sha: str = ""


Notes = dict[int, tuple[list[str], list[str]]]  # artifact -> (notices, history), newest first; this run only


@dataclass
class RunContext:
    """What one run adds to the guides: transient notes, new violation records, accepted commands."""

    now: datetime
    notes: Notes = field(default_factory=dict)
    found: dict[int, list[Record]] = field(default_factory=dict)
    accepted: dict[int, set[str]] = field(default_factory=dict)


def _guide(
    ws: Workspace, graph: Graph, snap: Snapshot, derived: Derived, ctx: RunContext
) -> tuple[str | None, list[Record]]:
    """The guide with the persisted notices carried over and resolved, and those notices.

    ``(None, [])`` when the persisted state is unknown (the guide is then not rewritten).
    """
    state = ws.states.get(snap.number, GuideState())
    if state is None:
        return None, []
    number = snap.number
    records = persisted.update(
        state.records, ctx.found.get(number, []), snap, derived, graph, ws.cfg, ctx.now, ctx.accepted.get(number)
    )
    notices, history = ctx.notes.get(number, ([], []))
    changes = protected_changes(snap, ws.cfg)
    texts = [*notices, *([protected_notice(changes)] if changes else []), *persisted.render(records, snap.is_pr)]
    pending = snap.head_sha if changes else ""  # the files listed now are what `/oct accept-paths` covers
    data = persisted.state_data(records, ws.acceptances.get(number) or state.accepted, pending)
    steps = next_steps(snap, derived, ws.cfg, graph)
    return render_guide(snap, derived, steps, texts, history, cfg=ws.cfg, data=data), records


def gate_problems(
    snap: Snapshot, cfg: Config, block_current: bool, has_block: bool, state: GuideState | None
) -> list[str]:
    """Why the `oct-status` gate of a pull request fails; empty when it passes (one rule for check and status).

    Fail closed: an unreadable guide (unknown notices) is a problem.
    """
    problems: list[str] = []
    if has_block and not block_current:
        problems.append("The status block is missing or out of date.")
    if changes := protected_changes(snap, cfg):
        count = len({path for _, path in changes})
        problems.append(f"Automation pushed to {count} protected path(s) without a maintainer's `/oct accept-paths`.")
    if not has_block:
        return problems  # an announcement carries no block and no guide
    if state is None:
        problems.append("The guide comment could not be read, so open violations cannot be ruled out.")
    elif blocks := persisted.blocking(state.records, snap.is_pr):
        rules = ", ".join(sorted({r.rule for r in blocks}))
        problems.append(f"Open violation(s) at ladder level 3 or higher: {rules}. Fix them or ask for `/oct override`.")
    return problems


def _open_pr(snap: Snapshot) -> bool:
    return snap.is_pr and snap.state == "open" and not snap.merged


async def _converge(
    ws: Workspace, targets: list[int], dry_run: bool, ctx: RunContext | None = None, *, comments: bool = True
) -> list[Outcome]:
    ctx = ctx or RunContext(_utcnow())
    graph = ws.graph()
    outcomes: list[Outcome] = []
    for number in targets:
        snap = graph.snapshots.get(number)
        if snap is None:
            continue
        derived = graph.derived.get(number)
        if derived is None:  # announcement: nothing is ever written
            gate = gate_problems(snap, ws.cfg, True, False, None) if _open_pr(snap) else None
            outcomes.append(Outcome(number, None, gate=gate, head_sha=snap.head_sha))
            continue
        block = render_block(snap, derived, graph, ws.cfg)
        guide, records = _guide(ws, graph, snap, derived, ctx) if comments else (None, [])
        with_comments = comments and guide is not None
        writes = await apply_state(ws.api, snap, derived, block, guide, ws.cfg, dry_run, comments=with_comments)
        unresolved = parse_prose_edges(number, snap.body)[1]
        gate = None
        if _open_pr(snap):
            # The state after this run: written blocks are current, the notices are the updated ones.
            in_comment = getattr(ws.cfg.automation.get(snap.author), "block_location", "body") == "comment"
            current = (not dry_run and (with_comments or not in_comment)) or (
                not in_comment and splice_block(snap.body, block or "") == snap.body
            )
            state = GuideState(tuple(records)) if with_comments else None
            gate = gate_problems(snap, ws.cfg, current, block is not None, state)
        outcomes.append(Outcome(number, derived, block, writes, unresolved, gate, snap.head_sha))
    return outcomes


def _fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}markdown\n{text}\n{fence}"


def _inline(text: str) -> str:
    return "`" + " ".join(text.replace("`", "'").split()) + "`"


def _summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path and lines:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def _warning_lines(ws: Workspace) -> list[str]:
    return [f"> {w}" for w in ws.warnings]


def _outcome_lines(outcome: Outcome, dry_run: bool, with_block: bool) -> list[str]:
    state = "dry-run, planned" if dry_run else "performed"
    lines = [f"### #{outcome.number}"]
    if outcome.derived is None:
        return [*lines, "", "Announcement: nothing is written.", ""]
    waits = ", ".join(sorted(w.value for w in outcome.derived.waits)) or "none"
    lines += ["", f"Phase `{outcome.derived.phase.value}`, waiting on: {waits}.", ""]
    lines += [f"Writes ({state}):"] if outcome.writes else ["No writes needed."]
    lines += [f"- {_inline(w)}" for w in outcome.writes]
    if outcome.unresolved:
        lines += ["", "Unresolved references:", *[f"- {_inline(u)}" for u in outcome.unresolved]]
    if with_block and outcome.block:
        lines += ["", _fence(outcome.block)]
    return [*lines, ""]


@dataclass
class CommandReport:
    command: commands.Command
    actor: str
    ok: bool
    message: str
    writes: list[str]
    notes: Notes
    rejected: str | None = None  # an invalid declaration (violation V07): `/oct <name> was rejected: <why>`


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _open_ledger(ws: Workspace, dry_run: bool, clock: Callable[[], datetime]) -> Ledger:
    """The ledger on the locked ledger issue (created in write mode when missing)."""
    try:
        number = await ensure_ledger_issue(
            ws.api, dry_run=dry_run, bot_logins=ws.cfg.bot_logins, configured=ws.cfg.ledger_issue
        )
    except LedgerIssueError as exc:
        raise LedgerError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise LedgerError(f"ledger issue lookup failed ({type(exc).__name__})") from exc
    if number == 0:
        raise LedgerError("the ledger issue does not exist yet (run the label sync)")
    return Ledger(ws.api, number, clock, cfg=ws.cfg)


async def _handle_command(
    ws: Workspace, number: int, payload: dict[str, Any], dry_run: bool, clock: Callable[[], datetime] = _utcnow
) -> CommandReport | None:
    """Parse, authorize and execute the `/oct` command of a new comment; ``None`` if there is none."""
    comment = payload.get("comment")
    if payload.get("action") != "created" or not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
        return None
    cmd = commands.parse_command(comment["body"])
    actor = _nested(payload, "comment", "user", "login")
    if cmd is None or not isinstance(actor, str) or not commands.valid_login(actor):
        return None
    snap = ws.graph().snapshots.get(number)
    if snap is None:
        return None
    comment_id = _number(comment.get("id"))
    if comment_id is not None:
        await commands.react(ws.api, comment_id, "eyes", dry_run=dry_run)
    allowed, reason = await commands.authorize_detailed(ws.api, actor, cmd, ws.cfg)
    writes: list[str] = []
    rejected: str | None = None
    if allowed:
        derived = ws.graph().derived.get(number)
        try:
            result = await commands.execute(ws.api, cmd, snap, derived, actor, cfg=ws.cfg, dry_run=dry_run)
            if not result.ok and result.precondition and cmd.name in commands.DECLARATION_COMMANDS:
                rejected = f"/oct {cmd.name} was rejected: {result.message}"
            if result.ok and cmd.name == "override":
                result = await _record_override(ws, number, actor, cmd.args, result, dry_run, clock)
            if result.ok:
                writes = await commands.apply_declaration(ws.api, number, result.declare, dry_run=dry_run)
                writes += result.effects
                add, remove = result.declare.get("add", []), result.declare.get("remove", [])
                ws.patch(number, add, remove, result.no_spec_reason, result.accept_paths)
                if result.accept_paths:  # stored in the guide data, the log of the acknowledgement
                    ws.acceptances[number] = Acceptance(result.accept_paths, actor, clock())
                    writes.append(f"acknowledge protected paths up to {result.accept_paths[:7]} in the guide data")
        except httpx.HTTPError as exc:  # fail closed
            result = commands.Outcome(False, f"the command failed ({type(exc).__name__})")
    else:
        result = commands.Outcome(False, reason)
    if comment_id is not None:
        await commands.react(ws.api, comment_id, "+1" if result.ok else "-1", dry_run=dry_run)
    if result.ok:
        notes: Notes = {number: ([], [f"/oct {cmd.name} by {actor}: {result.message}"])}
    else:
        notes = {number: ([f"/oct {cmd.name} by {actor} was rejected: {result.message}"], [])}
    return CommandReport(cmd, actor, result.ok, result.message, writes, notes, rejected)


async def _record_override(
    ws: Workspace,
    number: int,
    actor: str,
    reason: str,
    result: commands.Outcome,
    dry_run: bool,
    clock: Callable[[], datetime],
) -> commands.Outcome:
    """Log `/oct override` in the ledger (never in dry-run); fails closed when the ledger is unwritable."""
    if not strikes_active(ws.cfg, clock().date()):  # nothing to override yet: the ledger is not touched
        return commands.Outcome(
            True, f"override accepted and logged here only: strikes are not active yet ({reason})", log=result.log
        )
    if dry_run:
        return commands.Outcome(True, f"would record the override in the ledger (dry-run): {reason}", log=result.log)
    try:
        await (await _open_ledger(ws, False, clock)).record_override(actor, number, reason)
    except LedgerError as exc:
        return commands.Outcome(False, f"the override could not be recorded in the ledger: {exc}")
    return commands.Outcome(True, f"override recorded and effective: {reason}", log=result.log)


async def _closed_by_change(api: GitHubApi, number: int) -> bool | None:
    """Whether the latest `closed` event of an issue came from a merged change (it carries a commit).

    ``None`` when the timeline cannot be read: the caller then does not charge anything.
    """
    try:
        events = await _paged(api, f"/issues/{number}/events", {})
    except (httpx.HTTPError, ValueError):
        return None
    closed = [e for e in events if isinstance(e, dict) and e.get("event") == "closed"]
    return bool(closed[-1].get("commit_id")) if closed else None


async def _event_facts(
    ws: Workspace, snap: Snapshot, derived: Derived, payload: dict[str, Any], report: CommandReport | None
) -> EventFacts:
    """The actor's own change in this event; every value comes from the untrusted payload and is validated."""
    sender = _nested(payload, "sender", "login")
    action = payload.get("action")
    label = _nested(payload, "label", "name")
    before = _nested(payload, "changes", "body", "from")
    reason = _nested(payload, "issue", "state_reason")
    closed_by: bool | None = None
    if action == "closed" and not snap.is_pr and reason == "completed" and derived.phase == Phase.VERIFICATION:
        closed_by = await _closed_by_change(ws.api, snap.number)
    return EventFacts(
        action=action if isinstance(action, str) else "",
        actor=sender if isinstance(sender, str) and (commands.valid_login(sender) or sender.endswith("[bot]")) else "",
        label=label if isinstance(label, str) else "",
        body_before=before if isinstance(before, str) else None,
        rejected=report.rejected if report is not None else None,
        state_reason=reason if isinstance(reason, str) else None,
        closed_by_change=closed_by,
    )


@dataclass
class ViolationReport:
    records: list[Record] = field(default_factory=list)  # for the guide data of the event's artifact
    lines: list[str] = field(default_factory=list)  # job summary
    reverts: list[Violation] = field(default_factory=list)  # level >= 3 on an issue: undo the change


async def _violation_notes(
    ws: Workspace,
    number: int,
    payload: dict[str, Any],
    report: CommandReport | None,
    dry_run: bool,
    clock: Callable[[], datetime],
) -> ViolationReport:
    """Detect violations of the event's artifact and count them in the ledger.

    Fail closed: when the ledger cannot be read nothing is escalated beyond level 1 and nothing is
    recorded. Before ``strikes_enabled_from`` the ledger is not touched at all, so every notice stays at
    level 1 (no block, no revert).
    """
    graph = ws.graph()
    snap, derived = graph.snapshots.get(number), graph.derived.get(number)
    if snap is None or derived is None:
        return ViolationReport()
    actor_class = classify_actor(snap, ws.cfg)
    found = detect(snap, derived, graph, ws.cfg, actor_class, await _event_facts(ws, snap, derived, payload, report))
    if not found:
        return ViolationReport()
    ledger: Ledger | None = None
    lines = ["### Violations", ""]
    status = "strikes are not active: nothing is recorded"
    if strikes_active(ws.cfg, clock().date()):
        try:
            ledger = await _open_ledger(ws, dry_run, clock)
            await ledger.load()  # read the window once, so a failure shows here
        except LedgerError as exc:
            ledger, status = None, f"ledger unavailable ({exc}): no escalation beyond level 1, nothing recorded"
            ws.warnings.append(f"WARNING: {status}")
        else:
            status = "dry-run: nothing is recorded" if dry_run else "recorded"
    out = ViolationReport()
    for v in found:
        level, overridden = 0, False
        if ledger is not None:
            pairs = [(w.artifact, w.rule) for w in found if w.user == v.user]
            level = await ledger.ordinal(v.user, v.artifact, v.rule, pairs)
            overridden = await ledger.is_overridden(v.user, v.artifact, v.rule)
            if not dry_run:
                try:
                    if overridden:
                        await ledger.renew_override(v.artifact)  # the state violation persists
                    else:
                        await ledger.record(v)
                except LedgerError as exc:
                    ws.warnings.append(f"WARNING: violation {v.rule} not recorded: {exc}")
        notice = escalate(v, level, overridden)
        out.records.append(persisted.record_for(v, notice.level, overridden, clock()))
        if notice.revert(snap.is_pr) and not overridden:
            out.reverts.append(v)
        flags = " blocks" if notice.blocks(snap.is_pr) else " revert" if notice.revert(snap.is_pr) else ""
        lines.append(f"- {_inline(v.rule)} by {_inline(v.user)}: level {notice.level}{flags}; {status}")
    out.lines = [*lines, ""]
    return out


async def _revert(ws: Workspace, number: int, reverts: list[Violation], dry_run: bool) -> list[str]:
    """Undo a hand-edited fact label on an issue at ladder level 3 (design section 10).

    Convergence would heal the label as well, except a phase label whose history is unreadable; the
    event names the label, so it is undone here in every case. The block (V03) is restored by the
    convergence that follows.
    """
    graph = ws.graph()
    snap, derived = graph.snapshots.get(number), graph.derived.get(number)
    if snap is None or derived is None:
        return []
    want = desired_labels(derived)
    writes: list[str] = []
    for v in reverts:
        label = v.key
        if v.rule != "V02" or not label:
            continue
        if label in snap.labels and label not in want:
            if not dry_run:
                resp = await ws.api.request("DELETE", f"/issues/{number}/labels/{quote(label, safe='')}")
                if resp.status_code != 404:
                    resp.raise_for_status()
            ws.patch(number, [], [label])
            writes.append(f"revert: remove label {label} (V02, level 3)")
        elif label not in snap.labels and label in want:
            if not dry_run:
                resp = await ws.api.request("POST", f"/issues/{number}/labels", json={"labels": [label]})
                resp.raise_for_status()
            ws.patch(number, [label], [])
            writes.append(f"revert: restore label {label} (V02, level 3)")
    return writes


def _command_lines(report: CommandReport, dry_run: bool) -> list[str]:
    state = "dry-run, planned" if dry_run else "performed"
    verdict = "accepted" if report.ok else "rejected"
    lines = [f"### Command {_inline('/oct ' + report.command.name)} by {_inline(report.actor)}: {verdict}", ""]
    lines += [_inline(report.message), ""]
    if report.writes:
        lines += [f"Writes ({state}):", *[f"- {_inline(w)}" for w in report.writes], ""]
    return lines


async def run_event(
    api: GitHubApi,
    cfg: Config,
    event_name: str,
    payload: dict[str, Any],
    dry_run: bool,
    clock: Callable[[], datetime] = _utcnow,
) -> int:
    """Process one webhook event: recompute the artifact and its connected component (capped).

    In write mode every open pull request of the run gets the commit status `oct-status` on its head
    (see ``post_gate_statuses``); a dry run only reports the gate in the job summary.
    """
    if is_own_event(event_name, payload, set(cfg.bot_logins)):
        print("ignored: event caused by our own write")
        return EXIT_OK
    if event_name in _DISCUSSION_EVENTS:
        print("ignored: discussions are not handled yet")
        return EXIT_OK
    number = await resolve_artifact(api, event_name, payload)
    if number is None:
        print("ignored: the event does not name an artifact")
        return EXIT_OK
    ws = Workspace(api, cfg)
    component = await walk_component(number, ws.fan_out, cfg.fan_out_cap)
    targets = [number, *sorted(component - {number})]
    report = await _handle_command(ws, number, payload, dry_run, clock) if event_name == "issue_comment" else None
    violations = await _violation_notes(ws, number, payload, report, dry_run, clock)
    reverted = await _revert(ws, number, violations.reverts, dry_run)
    ctx = RunContext(
        clock(),
        notes=report.notes if report else {},
        found={number: violations.records},
        accepted={number: {report.command.name}} if report and report.ok else {},
    )
    outcomes = await _converge(ws, targets, dry_run, ctx)
    mode = "dry-run" if dry_run else "write"
    summary = [f"## OCT status ({mode}): event `{event_name}` on #{number}", "", *_warning_lines(ws), ""]
    summary += violations.lines
    if reverted:
        state = "dry-run, planned" if dry_run else "performed"
        summary += [f"Reverted ({state}):", *[f"- {_inline(w)}" for w in reverted], ""]
    if report is not None:
        summary += _command_lines(report, dry_run)
    statuses = await post_gate_statuses(api, outcomes, dry_run, ws.warnings)
    for outcome in outcomes:
        summary += _outcome_lines(outcome, dry_run, with_block=True)
        print(f"#{outcome.number}: {len(outcome.writes)} write(s) {'planned' if dry_run else 'performed'}")
    summary += _status_lines(statuses, dry_run)
    summary += [f"> {w}" for w in ws.warnings if w.startswith("WARNING: commit status")]
    if not outcomes:
        print(f"#{number}: not found, skipped")
        summary.append(f"#{number} was not found; nothing to do.")
    _summary(summary)
    return EXIT_OK


STATUS_CONTEXT = "oct-status"


def _run_url() -> str | None:
    server, repo, run = (os.environ.get(k, "") for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    if server.startswith("https://") and "/" in repo and run.isdigit():
        return f"{server}/{repo}/actions/runs/{run}"
    return None


async def post_gate_statuses(
    api: GitHubApi, outcomes: list[Outcome], dry_run: bool, warnings: list[str]
) -> list[tuple[int, str, str]]:
    """Publish the gate of every open PR as the commit status `oct-status` on its head SHA.

    This status (not the job of a `pull_request_target` run, which attaches to the base commit) is the
    required check. A new push changes the head, so a head without a status is pending until the
    `synchronize` event or the daily audit posts one. Never written in a dry run or through a read-only
    client (the summary shows what would be posted); a failed post is a warning.
    Returns (number, state, description).
    """
    posted: list[tuple[int, str, str]] = []
    for outcome in outcomes:
        if outcome.gate is None or not _SHA.fullmatch(outcome.head_sha):
            continue
        state = "failure" if outcome.gate else "success"
        description = (outcome.gate[0] if outcome.gate else "Status block current, nothing blocks")[:140]
        posted.append((outcome.number, state, description))
        if dry_run or api.read_only:
            continue
        body: dict[str, str] = {"state": state, "context": STATUS_CONTEXT, "description": description}
        if url := _run_url():
            body["target_url"] = url
        try:
            (await api.request("POST", f"/statuses/{outcome.head_sha}", json=body)).raise_for_status()
        except httpx.HTTPError as exc:
            warnings.append(f"WARNING: commit status for #{outcome.number} not posted ({type(exc).__name__})")
    return posted


def _status_lines(statuses: list[tuple[int, str, str]], dry_run: bool) -> list[str]:
    if not statuses:
        return []
    verb = "would post (dry-run)" if dry_run else "posted"
    lines = [f"Commit status `{STATUS_CONTEXT}` {verb}:"]
    return [*lines, *[f"- #{n}: {state}, {_inline(text)}" for n, state, text in statuses], ""]


async def _block_is_current(api: GitHubApi, cfg: Config, snap: Snapshot, block: str) -> bool:
    actor = cfg.automation.get(snap.author)
    if actor is not None and actor.block_location == "comment":
        guides = await _find_guides(api, snap.number, cfg.bot_logins)
        return bool(guides) and extract_block(guides[0].get("body") or "") == block
    return splice_block(snap.body, block) == snap.body


async def run_check(api: GitHubApi, cfg: Config, event_name: str, payload: dict[str, Any]) -> int:
    """Exit 1 when the artifact is not mergeable from the status system's view (report job).

    The required check is the commit status `oct-status` (``post_gate_statuses``) computed by the same
    ``gate_problems``; this job only reports, because a `pull_request_target` job attaches to the base commit.

    Red when the block is missing or stale, when automation pushed to protected paths without a
    maintainer's `/oct accept-paths`, or when an open violation notice at ladder level 3 or higher is
    persisted on the pull request (fix it or `/oct override`). Stdout carries fixed texts only.
    """
    number = await resolve_artifact(api, event_name, payload)
    if number is None:
        print("ok: the event does not name an artifact")
        return EXIT_OK
    ws = Workspace(api, cfg)
    await walk_component(number, ws.fan_out, cfg.fan_out_cap)
    graph = ws.graph()
    snap, derived = graph.snapshots.get(number), graph.derived.get(number)
    block = render_block(snap, derived, graph, cfg) if snap is not None and derived is not None else None
    heading = [f"## oct-status check: #{number}", ""]
    if snap is None or (block is None and not (snap.is_pr and protected_changes(snap, cfg))):
        print(f"ok: #{number} carries no block")
        return EXIT_OK
    current = block is None or await _block_is_current(api, cfg, snap, block)
    problems = gate_problems(snap, cfg, current, block is not None, ws.states.get(number, GuideState()))
    if not problems:
        print(f"ok: #{number} is current and nothing blocks it")
        _summary([*heading, "The status block is current and nothing blocks the check."])
        return EXIT_OK
    print(f"failed: #{number}: {len(problems)} problem(s), see the job summary")
    _summary([*heading, *[f"- {p}" for p in problems]])
    return EXIT_STALE


async def run_audit(
    api: GitHubApi,
    cfg: Config,
    dry_run: bool,
    clock: Callable[[], datetime] = _utcnow,
) -> int:
    """Recompute every open artifact and heal drift; returns how many artifacts needed a repair."""
    ws = Workspace(api, cfg)
    numbers = sorted({int(item["number"]) for item in await ws.open_items()})
    if ws.warnings and not dry_run:  # fail closed: never write on incomplete data
        ws.warnings.append("WARNING: audit forced to dry-run because the listing of open artifacts is incomplete")
        dry_run = True
    for number in numbers:
        await ws.neighbors(number)  # loads the artifact and its relations
    outcomes = await _converge(ws, numbers, dry_run, RunContext(clock()))
    repaired = [o for o in outcomes if o.writes]
    # Every open PR gets the status for its current head (heads pushed without an event in between).
    statuses = await post_gate_statuses(api, outcomes, dry_run, ws.warnings)
    mode = "dry-run" if dry_run else "write"
    summary = [
        f"## OCT status audit ({mode})",
        "",
        *_warning_lines(ws),
        f"{len(outcomes)} open artifacts checked, repaired {len(repaired)}.",
        "",
    ]
    for outcome in repaired:
        summary += _outcome_lines(outcome, dry_run, with_block=False)
    summary += _status_lines(statuses, dry_run)
    _summary(summary)
    for warning in ws.warnings:
        print(warning)
    print(f"audit: {len(outcomes)} open artifact(s) checked, repaired {len(repaired)}")
    return len(repaired)


# --- CLI ----------------------------------------------------------------------------------------


def _mode(args: argparse.Namespace) -> str:
    if args.labels:
        return "labels"
    if args.audit:
        return "audit"
    if args.backfill:
        if args.limit < 1:
            raise ConfigError("--limit must be a positive number of artifacts")
        return "backfill"
    if args.event or args.payload or args.check:
        if not (args.event and args.payload):
            raise ConfigError("--event and --payload must be given together (also with --check)")
        return "check" if args.check else "event"
    raise ConfigError("no mode selected (use --labels, --event/--payload, --check, --audit or --backfill)")


def _load_payload(path: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read event payload ({type(exc).__name__})") from exc
    if not isinstance(data, dict):
        raise ConfigError("event payload must be a JSON object")
    return data


async def _dispatch(
    args: argparse.Namespace, mode: str, payload: dict[str, Any], token: str, repo: str
) -> tuple[int, list[str]]:
    # Dry-run (shadow mode) and check can never write, enforced by the client itself.
    api = GitHubApi(token, repo, read_only=args.dry_run or mode == "check")
    if not api.read_only and not os.environ.get("BOT_PAT"):
        print("warning: write mode without BOT_PAT; writes use GITHUB_TOKEN (github-actions[bot])", file=sys.stderr)
    try:
        if mode == "labels":
            return EXIT_OK, await _run_labels(api, args.dry_run)
        cfg = load_config(CONFIG_PATH)
        if mode == "backfill":
            from oct_status.backfill import run_backfill  # imports this module

            state = Path(args.state or os.environ.get("OCT_BACKFILL_STATE") or DEFAULT_BACKFILL_STATE)
            return await run_backfill(api, cfg, state, args.limit, args.dry_run), []
        if mode == "audit":
            await run_audit(api, cfg, args.dry_run)
            return EXIT_OK, []
        if mode == "check":
            return await run_check(api, cfg, args.event, payload), []
        return await run_event(api, cfg, args.event, payload, args.dry_run), []
    finally:
        await api.aclose()


def cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        mode = _mode(args)
        payload = _load_payload(args.payload) if mode in ("event", "check") else {}
        token, repo = _credentials()
        code, lines = asyncio.run(_dispatch(args, mode, payload, token, repo))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except httpx.HTTPError as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        detail = f"HTTP {status}" if status else type(exc).__name__
        print(f"error: GitHub API request failed ({detail})", file=sys.stderr)
        return EXIT_API_ERROR
    _emit(lines)
    return code
