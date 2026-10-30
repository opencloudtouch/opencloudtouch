"""Rate-limited, resumable backfill of the open artifacts (design section 14, rollout step 2; MA-6).

The backfill brings the existing artifacts into the system: labels and the status block in the body,
derived from facts. It never creates or edits a comment (no notifications, no guide comment; a block
that lives in a pinned comment waits for the next event), never detects violations and never touches
the ledger. Two migrations happen here and nowhere else:

* Legacy readiness: a spec written before the Definition of Ready existed (no DoR section) that has a
  merged or open pull request, or carries the renamed legacy `wip` label, is declared `ready` by the
  bot; a bug or feature request with the legacy `wip` keeps the `triaged` floor. Phases then come
  from the facts (open draft PR: in progress, ready PR: in review, ...).
* Re-assertion: a phase label that is already right but was not written by our own accounts (for
  example one the label sync renamed from `wip`) is removed and added again by the bot, so the label
  history names the bot and later runs trust it (``Snapshot.bot_phase_labels``).

Progress is kept in a small JSON state file (no secrets: artifact numbers and a timestamp). A rate
limit (403 / 429) or another API error stops the run cleanly after saving the state; the next run
continues with the first artifact not done. A fixed minimum delay separates the artifacts.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .api import GitHubApi
from .apply import apply_state
from .config import Config
from .graph import parse_prose_edges
from .main import EXIT_API_ERROR, EXIT_OK, Workspace, _inline, _paged, _summary
from .model import EdgeType, Kind, Snapshot
from .render import render_block
from .rules import detect_kind, legacy_spec, spec_is_ready

MAX_RETRY_WAIT = 60.0  # a rate limit asking for longer stops the run (state saved) instead of waiting
MIN_DELAY = 2.0  # seconds between two artifacts (GitHub asks for at least one second between writes)
STATE_VERSION = 1
_LEGACY_STARTED = ("wip", "phase:in-progress")


@dataclass
class BackfillReport:
    processed: int = 0
    remaining: int = 0
    stopped: str | None = None  # why the run ended early
    retry_after: int | None = None  # seconds, after a rate limit
    already_done: int = 0  # skipped because the state file lists them
    unreadable: int = 0  # skipped, not done: label history or comments could not be read
    lines: list[str] = field(default_factory=list)


def load_state(path: Path) -> set[int]:
    """Numbers already done; an unreadable or foreign state file starts over (the work is idempotent)."""
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict) or data.get("v") != STATE_VERSION or not isinstance(data.get("done"), list):
        return set()
    return {n for n in data["done"] if isinstance(n, int) and not isinstance(n, bool) and n > 0}


def save_state(path: Path, done: set[int], now: datetime) -> None:
    """Write the state atomically (a crash never leaves half a file behind)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"v": STATE_VERSION, "done": sorted(done), "updated": now.isoformat()}), "utf-8")
    os.replace(tmp, path)


def legacy_view(snap: Snapshot, cfg: Config, parts: dict[int, set[int]]) -> Snapshot:
    """The snapshot with the legacy declarations the backfill makes (see the module docstring)."""
    if snap.is_pr or snap.state != "open" or snap.timeline_unknown:
        return snap
    labels, written = set(snap.labels), set(snap.bot_phase_labels)
    started = "wip" in labels or ("phase:in-progress" in labels and "phase:in-progress" not in written)
    kind = detect_kind(snap, cfg)
    if kind == Kind.SPEC and not spec_is_ready(snap):
        if started or (legacy_spec(snap.body) and parts.get(snap.number)):
            labels.add("phase:ready")
            written.add("phase:ready")  # the bot writes the declaration
    elif kind in (Kind.BUG, Kind.FEATURE_REQUEST) and started:
        labels.add("phase:triaged")
    return replace(snap, labels=frozenset(labels), bot_phase_labels=frozenset(written))


class LegacyWorkspace(Workspace):
    """A workspace that sees every artifact with the backfill's legacy declarations applied."""

    def __init__(self, api: GitHubApi, cfg: Config, parts: dict[int, set[int]]) -> None:
        super().__init__(api, cfg)
        self.parts = parts
        self.real: dict[int, Snapshot] = {}

    async def load(self, number: int) -> Snapshot | None:
        if number in self.real or number in self._snaps:
            return self._snaps.get(number)
        snap = await super().load(number)
        if snap is not None:
            self.real[number] = snap
            self._snaps[number] = legacy_view(snap, self.cfg, self.parts)
        return self._snaps[number]


async def legacy_parts(api: GitHubApi, warnings: list[str]) -> dict[int, set[int]]:
    """Issue number -> pull requests (open or merged) that name it in `Closes` / `Part of`."""
    parts: dict[int, set[int]] = {}
    for item in await _paged(api, "/issues", {"state": "all"}, warnings):
        pull = item.get("pull_request")
        if not isinstance(pull, dict) or (item.get("state") != "open" and not pull.get("merged_at")):
            continue
        for edge in parse_prose_edges(int(item["number"]), item.get("body") or "")[0]:
            if edge.type == EdgeType.IMPLEMENTS:
                parts.setdefault(edge.target, set()).add(int(item["number"]))
    return parts


async def _reassert(api: GitHubApi, real: Snapshot, label: str, dry_run: bool) -> list[str]:
    """Write a correct phase label again as the bot when the label history does not name our accounts.

    Issues only: a pull request's phase is always a fact and never a trusted floor.
    """
    if real.is_pr or real.timeline_unknown or label not in real.labels or label in real.bot_phase_labels:
        return []
    if not dry_run:
        resp = await api.request("DELETE", f"/issues/{real.number}/labels/{quote(label, safe='')}")
        if resp.status_code != 404:
            resp.raise_for_status()
        (await api.request("POST", f"/issues/{real.number}/labels", json={"labels": [label]})).raise_for_status()
    return [f"re-assert label {label} as the bot"]


def _cap_retry(api: GitHubApi) -> None:
    """Stop at a long rate limit (state saved, resumed later) instead of sleeping through it."""
    if api.max_retry_wait is None or api.max_retry_wait > MAX_RETRY_WAIT:
        api.max_retry_wait = MAX_RETRY_WAIT


class Unreadable(Exception):
    """The artifact's label history or comments could not be read: it is skipped and stays to do."""


async def _one(ws: LegacyWorkspace, number: int, dry_run: bool) -> list[str]:
    """Labels and block of one artifact; nothing for a missing artifact or an announcement."""
    if await ws.load(number) is None:
        return []
    if ws.real[number].timeline_unknown or ws.states.get(number) is None:
        raise Unreadable(number)
    await ws.neighbors(number)
    graph = ws.graph()
    snap, derived = graph.snapshots[number], graph.derived.get(number)
    if derived is None:
        return []
    real = ws.real[number]
    block = render_block(snap, derived, graph, ws.cfg)
    writes = await apply_state(ws.api, real, derived, block, None, ws.cfg, dry_run, comments=False)
    return writes + await _reassert(ws.api, real, derived.phase.label, dry_run)


def _rate_limit(resp: httpx.Response) -> int | None:
    """Seconds to wait when `resp` is a rate limit (primary or secondary), else ``None``."""
    if resp.status_code not in (403, 429):
        return None
    after = resp.headers.get("retry-after", "")
    if after.isdigit():
        return int(after)
    reset = resp.headers.get("x-ratelimit-reset", "")
    if resp.headers.get("x-ratelimit-remaining") == "0" and reset.isdigit():
        return max(int(reset) - int(time.time()), 1)
    return 60 if resp.status_code == 429 else None


async def _backfill(
    api: GitHubApi,
    cfg: Config,
    numbers: list[int],
    state_path: Path,
    clock: Callable[[], datetime],
    sleep: Callable[[float], Awaitable[None]],
    *,
    limit: int | None = None,
    dry_run: bool = False,
    parts: dict[int, set[int]] | None = None,
) -> BackfillReport:
    _cap_retry(api)
    done = load_state(state_path)
    todo = [n for n in numbers if n not in done]
    report = BackfillReport(already_done=len(numbers) - len(todo))
    ws = LegacyWorkspace(api, cfg, parts or {})
    try:
        if parts is None:
            ws.parts = await legacy_parts(api, ws.warnings)
        for index, number in enumerate(todo[:limit] if limit else todo):
            if index:
                await sleep(MIN_DELAY)
            try:
                writes = await _one(ws, number, dry_run)
            except Unreadable:
                report.unreadable += 1
                report.lines.append(f"- #{number}: skipped, label history or comments unreadable (retried next run)")
                continue
            report.processed += 1
            report.lines += [f"- #{number}: " + (", ".join(_inline(w) for w in writes) or "no writes needed")]
            if not dry_run:  # a dry run never marks an artifact as done
                done.add(number)
                save_state(state_path, done, clock())
    except httpx.HTTPStatusError as exc:
        wait = _rate_limit(exc.response)
        if wait is None:
            report.stopped = f"API error (HTTP {exc.response.status_code})"
        else:
            report.stopped, report.retry_after = "rate limit", wait
    except httpx.HTTPError as exc:
        report.stopped = f"API error ({type(exc).__name__})"
    report.lines += [f"> {w}" for w in ws.warnings]
    report.remaining = len([n for n in numbers if n not in done])
    return report


async def backfill(
    api: GitHubApi,
    cfg: Config,
    numbers: list[int],
    state_path: Path,
    clock: Callable[[], datetime],
    sleep: Callable[[float], Awaitable[None]],
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> int:
    """Backfill `numbers` in order, skipping those the state file lists; returns how many were processed."""
    report = await _backfill(api, cfg, numbers, state_path, clock, sleep, limit=limit, dry_run=dry_run)
    return report.processed


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def run_backfill(
    api: GitHubApi,
    cfg: Config,
    state_path: Path,
    limit: int,
    dry_run: bool,
    clock: Callable[[], datetime] = _utcnow,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    """One backfill batch over the open artifacts (issues first); prints `remaining: N`.

    Exit 0 when the batch finished or stopped at a rate limit (run again after the printed time),
    1 after another API error. The state is saved in both cases.
    """
    warnings: list[str] = []
    _cap_retry(api)
    try:
        items = await _paged(api, "/issues", {"state": "open"}, warnings)
    except httpx.HTTPStatusError as exc:
        wait = _rate_limit(exc.response)
        print(f"rate limited: retry after {wait} s" if wait is not None else "error: listing open artifacts failed")
        return EXIT_OK if wait is not None else EXIT_API_ERROR
    numbers = [int(i["number"]) for i in sorted(items, key=lambda i: ("pull_request" in i, int(i["number"])))]
    report = await _backfill(api, cfg, numbers, state_path, clock, sleep, limit=limit, dry_run=dry_run)
    mode = "dry-run" if dry_run else "write"
    summary = [f"## OCT status backfill ({mode})", "", *[f"> {w}" for w in warnings], *report.lines, ""]
    if report.stopped == "rate limit":
        print(f"rate limited: retry after {report.retry_after} s (the next run resumes)")
    elif report.stopped:
        print(f"stopped: {report.stopped} (the next run resumes)")
    counts = (
        f"processed {report.processed}, already done (state file): {report.already_done}, "
        f"skipped (unreadable): {report.unreadable}, remaining: {report.remaining}"
    )
    summary.append(counts)
    _summary(summary)
    print(f"backfill ({mode}): {counts}")
    return EXIT_API_ERROR if report.stopped and report.stopped != "rate limit" else EXIT_OK
