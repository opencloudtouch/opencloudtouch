"""Command line entry point of the OCT status system.

Modes: ``--labels`` (label sync), ``--event/--payload`` (one webhook event), ``--check`` (is the block of
the event's artifact current?) and ``--audit`` (heal drift on every open artifact).

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

import httpx

from oct_status import commands
from oct_status.api import GitHubApi
from oct_status.apply import _find_guides, apply_state, is_own_event
from oct_status.config import Config, load_config
from oct_status.facts import fetch_snapshot
from oct_status.graph import build_graph, parse_prose_edges, walk_component
from oct_status.guide import format_notice, next_steps, render_guide
from oct_status.labels_sync import ensure_ledger_issue, sync_labels
from oct_status.ledger import Ledger, LedgerError
from oct_status.model import Derived, Edge, Graph, Snapshot
from oct_status.render import extract_block, render_block, splice_block
from oct_status.rules import derive
from oct_status.violations import EventFacts, classify_actor, detect, escalate

LABELS_SPEC = Path(__file__).resolve().parent / "labels.yml"
CONFIG_PATH = Path(__file__).resolve().parent / "config.yml"

EXIT_OK = 0
EXIT_API_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_STALE = 1

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
    parser.add_argument("--dry-run", action="store_true", help="plan only, perform no writes")
    return parser


def _credentials() -> tuple[str, str]:
    # BOT_PAT is preferred when present (write mode, labels job); shadow-mode steps only get GITHUB_TOKEN.
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


async def _run_labels(api: GitHubApi, dry_run: bool) -> list[str]:
    ops = await sync_labels(api, LABELS_SPEC, dry_run=dry_run)
    ledger = await ensure_ledger_issue(api, dry_run=dry_run)
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
                self._snaps[number] = await self._with_no_spec(snap)
        return self._snaps[number]

    async def _with_no_spec(self, snap: Snapshot) -> Snapshot:
        if not snap.is_pr:
            return snap
        try:
            reason = await commands.find_no_spec(self.api, snap)
        except httpx.HTTPError:
            self.warnings.append(f"WARNING: comments of #{snap.number} unreadable; a /oct no-spec waiver is not seen")
            return snap
        return replace(snap, no_spec_reason=reason) if reason else snap

    def patch(self, number: int, add: list[str], remove: list[str], no_spec_reason: str | None = None) -> None:
        """Reflect a command's declaration in the loaded snapshot (the labels were written, or are planned)."""
        snap = self._snaps.get(number)
        if snap is None:
            return
        labels = (snap.labels - set(remove)) | set(add)
        self._snaps[number] = replace(
            snap, labels=frozenset(labels), no_spec_reason=no_spec_reason or snap.no_spec_reason
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


Notes = dict[int, tuple[list[str], list[str]]]  # artifact -> (notices, history), newest first


async def _converge(ws: Workspace, targets: list[int], dry_run: bool, notes: Notes | None = None) -> list[Outcome]:
    graph = ws.graph()
    outcomes: list[Outcome] = []
    for number in targets:
        snap = graph.snapshots.get(number)
        if snap is None:
            continue
        derived = graph.derived.get(number)
        if derived is None:  # announcement: nothing is ever written
            outcomes.append(Outcome(number, None))
            continue
        block = render_block(snap, derived, graph, ws.cfg)
        notices, history = (notes or {}).get(number, ([], []))
        guide = render_guide(snap, derived, next_steps(snap, derived, ws.cfg, graph), notices, history, cfg=ws.cfg)
        writes = await apply_state(ws.api, snap, derived, block, guide, ws.cfg, dry_run)
        unresolved = parse_prose_edges(number, snap.body)[1]
        outcomes.append(Outcome(number, derived, block, writes, unresolved))
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
        number = await ensure_ledger_issue(ws.api, dry_run=dry_run)
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
            if not result.ok and cmd.name in commands.DECLARATION_COMMANDS:
                rejected = f"/oct {cmd.name} was rejected: {result.message}"
            if result.ok and cmd.name == "override":
                result = await _record_override(ws, number, actor, cmd.args, result, dry_run, clock)
            if result.ok:
                writes = await commands.apply_declaration(ws.api, number, result.declare, dry_run=dry_run)
                writes += result.effects
                ws.patch(number, result.declare.get("add", []), result.declare.get("remove", []), result.no_spec_reason)
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
    if dry_run:
        return commands.Outcome(True, f"would record the override in the ledger (dry-run): {reason}", log=result.log)
    try:
        await (await _open_ledger(ws, False, clock)).record_override(actor, number, reason)
    except LedgerError as exc:
        return commands.Outcome(False, f"the override could not be recorded in the ledger: {exc}")
    return commands.Outcome(True, f"override recorded and effective: {reason}", log=result.log)


def _event_facts(payload: dict[str, Any], report: CommandReport | None) -> EventFacts:
    """The actor's own change in this event; every value comes from the untrusted payload and is validated."""
    sender = _nested(payload, "sender", "login")
    action = payload.get("action")
    label = _nested(payload, "label", "name")
    before = _nested(payload, "changes", "body", "from")
    return EventFacts(
        action=action if isinstance(action, str) else "",
        actor=sender if isinstance(sender, str) and (commands.valid_login(sender) or sender.endswith("[bot]")) else "",
        label=label if isinstance(label, str) else "",
        body_before=before if isinstance(before, str) else None,
        rejected=report.rejected if report is not None else None,
    )


def _merge_notes(first: Notes | None, second: Notes) -> Notes:
    merged: Notes = dict(first or {})
    for number, (notices, history) in second.items():
        old_notices, old_history = merged.get(number, ([], []))
        merged[number] = ([*old_notices, *notices], [*old_history, *history])
    return merged


async def _violation_notes(
    ws: Workspace,
    number: int,
    payload: dict[str, Any],
    report: CommandReport | None,
    dry_run: bool,
    clock: Callable[[], datetime],
) -> tuple[Notes, list[str]]:
    """Detect violations of the event's artifact, count them in the ledger and render the guide notices.

    Fail closed: when the ledger cannot be read nothing is escalated beyond level 1 and nothing is
    recorded. Before ``strikes_enabled_from`` the ledger is not touched at all.
    """
    graph = ws.graph()
    snap, derived = graph.snapshots.get(number), graph.derived.get(number)
    if snap is None or derived is None:
        return {}, []
    association = _nested(payload, "pull_request", "author_association") or _nested(
        payload, "issue", "author_association"
    )
    actor_class = classify_actor(snap, association if isinstance(association, str) else None, ws.cfg)
    found = detect(snap, derived, graph, ws.cfg, actor_class, _event_facts(payload, report))
    if not found:
        return {}, []
    ledger: Ledger | None = None
    lines = ["### Violations", ""]
    status = "strikes are not active: nothing is recorded"
    start = ws.cfg.strikes_enabled_from
    if start is not None and clock().date() >= start:
        try:
            ledger = await _open_ledger(ws, dry_run, clock)
            await ledger.load()  # read the window once, so a failure shows here
        except LedgerError as exc:
            ledger, status = None, f"ledger unavailable ({exc}): no escalation beyond level 1, nothing recorded"
            ws.warnings.append(f"WARNING: {status}")
        else:
            status = "dry-run: nothing is recorded" if dry_run else "recorded"
    notices: list[str] = []
    for v in found:
        level, overridden = 0, False
        if ledger is not None:
            pairs = {(w.artifact, w.rule) for w in found if w.user == v.user}
            level = await ledger.level_after(v.user, pairs)
            overridden = await ledger.is_overridden(v.user, v.artifact, v.rule)
            if not dry_run and not overridden:
                try:
                    await ledger.record(v)
                except LedgerError as exc:
                    ws.warnings.append(f"WARNING: violation {v.rule} not recorded: {exc}")
        notice = escalate(v, level, overridden)
        notices.append(format_notice(notice, snap.is_pr))
        flags = " blocks" if notice.blocks(snap.is_pr) else " revert" if notice.revert(snap.is_pr) else ""
        lines.append(f"- {_inline(v.rule)} by {_inline(v.user)}: level {notice.level}{flags}; {status}")
    return {number: (notices, [])}, [*lines, ""]


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
    """Process one webhook event: recompute the artifact and its connected component (capped)."""
    if is_own_event(event_name, payload, set(cfg.bot_logins)):
        print("ignored: event caused by our own write")
        return EXIT_OK
    if event_name in _DISCUSSION_EVENTS:
        print("ignored: discussions are not handled in this milestone")
        return EXIT_OK
    number = await resolve_artifact(api, event_name, payload)
    if number is None:
        print("ignored: the event does not name an artifact")
        return EXIT_OK
    ws = Workspace(api, cfg)
    component = await walk_component(number, ws.neighbors, cfg.fan_out_cap)
    targets = [number, *sorted(component - {number})]
    report = await _handle_command(ws, number, payload, dry_run, clock) if event_name == "issue_comment" else None
    violation_notes, violation_lines = await _violation_notes(ws, number, payload, report, dry_run, clock)
    outcomes = await _converge(ws, targets, dry_run, _merge_notes(report.notes if report else None, violation_notes))
    mode = "dry-run" if dry_run else "write"
    summary = [f"## OCT status ({mode}): event `{event_name}` on #{number}", "", *_warning_lines(ws), ""]
    summary += violation_lines
    if report is not None:
        summary += _command_lines(report, dry_run)
    for outcome in outcomes:
        summary += _outcome_lines(outcome, dry_run, with_block=True)
        print(f"#{outcome.number}: {len(outcome.writes)} write(s) {'planned' if dry_run else 'performed'}")
    if not outcomes:
        print(f"#{number}: not found, skipped")
        summary.append(f"#{number} was not found; nothing to do.")
    _summary(summary)
    return EXIT_OK


async def _block_is_current(api: GitHubApi, cfg: Config, snap: Snapshot, block: str) -> bool:
    actor = cfg.automation.get(snap.author)
    if actor is not None and actor.block_location == "comment":
        guides = await _find_guides(api, snap.number, cfg.bot_logins)
        return bool(guides) and extract_block(guides[0].get("body") or "") == block
    return splice_block(snap.body, block) == snap.body


async def run_check(api: GitHubApi, cfg: Config, event_name: str, payload: dict[str, Any]) -> int:
    """Exit 1 when the artifact's block is missing or stale (the future required check)."""
    number = await resolve_artifact(api, event_name, payload)
    if number is None:
        print("ok: the event does not name an artifact")
        return EXIT_OK
    ws = Workspace(api, cfg)
    await walk_component(number, ws.neighbors, cfg.fan_out_cap)
    graph = ws.graph()
    snap, derived = graph.snapshots.get(number), graph.derived.get(number)
    block = render_block(snap, derived, graph, cfg) if snap is not None and derived is not None else None
    if snap is None or block is None:
        print(f"ok: #{number} carries no block")
        return EXIT_OK
    if await _block_is_current(api, cfg, snap, block):
        print(f"ok: status block of #{number} is current")
        _summary([f"## oct-status check: #{number}", "", "The status block is current."])
        return EXIT_OK
    print(f"stale: status block of #{number} is missing or out of date")
    _summary([f"## oct-status check: #{number}", "", "The status block is missing or out of date."])
    return EXIT_STALE


async def run_audit(api: GitHubApi, cfg: Config, dry_run: bool) -> int:
    """Recompute every open artifact and heal drift; returns how many artifacts needed a repair."""
    ws = Workspace(api, cfg)
    numbers = sorted({int(item["number"]) for item in await ws.open_items()})
    if ws.warnings and not dry_run:  # fail closed: never write on incomplete data
        ws.warnings.append("WARNING: audit forced to dry-run because the listing of open artifacts is incomplete")
        dry_run = True
    for number in numbers:
        await ws.neighbors(number)  # loads the artifact and its relations
    outcomes = await _converge(ws, numbers, dry_run)
    repaired = [o for o in outcomes if o.writes]
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
    if args.event or args.payload or args.check:
        if not (args.event and args.payload):
            raise ConfigError("--event and --payload must be given together (also with --check)")
        return "check" if args.check else "event"
    raise ConfigError("no mode selected (use --labels, --event/--payload, --check or --audit)")


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
    # Shadow mode: dry-run and check can never write, enforced by the client itself.
    api = GitHubApi(token, repo, read_only=args.dry_run or mode == "check")
    try:
        if mode == "labels":
            return EXIT_OK, await _run_labels(api, args.dry_run)
        cfg = load_config(CONFIG_PATH)
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
