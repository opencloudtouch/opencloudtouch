"""Render the examples of docs/WORKFLOW.md from the frozen fixtures, so the handbook cannot drift.

Read-only and offline: the recorded REST responses in ``tests/fixtures/`` are replayed, the real
derivation, block, label and guide functions run on them. Usage, from ``scripts/``::

    python -m oct_status.tools.render_doc_snippets            # print every snippet
    python -m oct_status.tools.render_doc_snippets --write    # update docs/WORKFLOW.md in place

In the handbook each snippet sits between ``<!-- snippet:<name> -->`` and ``<!-- /snippet -->``;
``tests/test_docs_snippets.py`` compares them byte for byte with this module's output.

Fixture bodies were sanitized at capture time: only their reference lines (``Part of #n``,
``Depends on #n``, bare ``#n``) are kept, so no Definition of Ready or Done checklist appears.
#570-#572 were never recorded; their refs, titles and draft flag come from the GitHub API
(read on 2026-10-30), everything else about them is empty. Steps marked as projections apply one
stated change to the recorded state; the actor of a projected command is the placeholder
``a-maintainer``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import replace as _with
from datetime import datetime, timezone
from pathlib import Path

import httpx

from oct_status import notices as persisted
from oct_status.api import GitHubApi
from oct_status.apply import desired_labels, guide_content
from oct_status.commands import execute, parse_command
from oct_status.config import Config, load_config
from oct_status.facts import fetch_snapshot
from oct_status.graph import build_graph
from oct_status.guide import format_notice, next_steps, render_guide
from oct_status.model import Graph, Review, Snapshot
from oct_status.render import render_block
from oct_status.rules import derive
from oct_status.violations import Notice, Violation, classify_actor, detect, escalate

PACKAGE = Path(__file__).resolve().parent.parent
FIXTURES = PACKAGE / "tests" / "fixtures"
DOC = PACKAGE.parent.parent / "docs" / "WORKFLOW.md"
REPO = "opencloudtouch/opencloudtouch"
RECORDED = (498, 537, 560, 573, 574, 575)
# (base ref, head ref, title) of the stack PRs that were not recorded; all three are drafts.
UNRECORDED = {
    570: (
        "claude/gifted-bohr-b225kf",
        "feat/device-settings-backend",
        "feat(devices): add device settings API for language, clock and power saving",
    ),
    571: (
        "feat/device-settings-backend",
        "feat/stream-recovery-backend",
        "feat(streamrecovery): add opt-in watchdog that resumes dropped radio presets",
    ),
    572: (
        "feat/stream-recovery-backend",
        "feat/stream-recovery-frontend",
        "feat(frontend): add stream recovery section to the settings page",
    ),
}
MAINTAINER = "a-maintainer"  # placeholder actor of projected commands
OWNED = ("phase:", "wait:", "resolution:")
_SNIPPET = re.compile(r"<!-- snippet:([a-z0-9-]+) -->\n(.*?)<!-- /snippet -->", re.DOTALL)

Snaps = dict[int, Snapshot]


def _routes() -> dict[str, object]:
    routes: dict[str, object] = {}
    for number in RECORDED:
        routes.update(json.loads((FIXTURES / f"{number}.json").read_text(encoding="utf-8")))
    for key in list(routes):
        if match := re.fullmatch(r"GET (.*)/pulls/(\d+)", key):
            routes.setdefault(f"GET {match[1]}/pulls/{match[2]}/commits", [])  # never recorded
    return routes


def _api() -> GitHubApi:
    routes = _routes()

    def handle(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.path}"
        if key not in routes:
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(200, json=routes[key])

    return GitHubApi("offline", REPO, transport=httpx.MockTransport(handle))


def _cfg() -> Config:
    return load_config(PACKAGE / "config.yml")


async def recorded() -> Snaps:
    """The recorded state (captured 2026-10-29) plus the unrecorded stack PRs as drafts."""
    api = _api()
    snaps: Snaps = {n: await fetch_snapshot(api, n, use_graphql=False) for n in RECORDED}
    template = snaps[574]
    for number, (base, head, title) in UNRECORDED.items():
        snaps[number] = _with(
            template,
            number=number,
            title=title,
            body="",
            base_ref=base,
            head_ref=head,
            head_sha="",
            reviews=(),
            checks=(),
            closing_refs=(),
        )
    return snaps


def graph_of(snaps: Snaps, cfg: Config) -> Graph:
    graph = build_graph(snaps)
    for number, snap in snaps.items():
        if (derived := derive(snap, graph, cfg)) is not None:
            graph.derived[number] = derived
    return graph


def fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    marks = "`" * max(3, longest + 1)
    return f"{marks}markdown\n{text.rstrip(chr(10))}\n{marks}"


def _labels(graph: Graph, number: int) -> str:
    snap, derived = graph.snapshots[number], graph.derived[number]
    kept = {lb for lb in snap.labels if not lb.startswith(OWNED)}
    names = sorted(kept | desired_labels(derived))
    return "Labels: " + ", ".join(f"`{n}`" for n in names)


def _block(graph: Graph, number: int, cfg: Config) -> str:
    block = render_block(graph.snapshots[number], graph.derived[number], graph, cfg)
    assert block is not None
    return fence(block)


def _guide(
    graph: Graph,
    number: int,
    cfg: Config,
    *,
    history: list[str] | None = None,
    records: list[persisted.Record] | None = None,
) -> str:
    """The guide comment as ``main._guide`` builds it (and, for Dependabot, the pinned comment)."""
    snap, derived = graph.snapshots[number], graph.derived[number]
    steps = next_steps(snap, derived, cfg, graph)
    texts = persisted.render(records or [], snap.is_pr)
    data = persisted.state_data(records or [], None)
    guide = render_guide(snap, derived, steps, texts, history or [], cfg=cfg, data=data)
    content = guide_content(snap, render_block(snap, derived, graph, cfg), guide, cfg)
    return fence(content or guide)


def _violations(graph: Graph, number: int, cfg: Config, when: datetime) -> list[persisted.Record]:
    """Level-1 records of the violations an event on `number` reports (strikes are not active)."""
    snap, derived = graph.snapshots[number], graph.derived[number]
    found = detect(snap, derived, graph, cfg, classify_actor(snap, cfg))
    return [persisted.record_for(v, escalate(v, 0).level, False, when) for v in found]


def _resolved(before: Graph, after: Graph, number: int, cfg: Config, when: datetime) -> list[persisted.Record]:
    """The persisted records of `before`, carried into a later run on `after` (resolves what no longer holds)."""
    snap, derived = after.snapshots[number], after.derived[number]
    return persisted.update(_violations(before, number, cfg, when), [], snap, derived, after, cfg, when)


async def _command(snaps: Snaps, number: int, text: str, cfg: Config) -> tuple[Snaps, str]:
    """Snapshots after an accepted command of the placeholder maintainer, and its history line."""
    cmd = parse_command(text)
    assert cmd is not None
    graph = graph_of(snaps, cfg)
    outcome = await execute(_api(), cmd, snaps[number], graph.derived.get(number), MAINTAINER, cfg=cfg)
    assert outcome.ok, outcome.message
    labels = (snaps[number].labels | set(outcome.declare.get("add", []))) - set(outcome.declare.get("remove", []))
    changed = dict(snaps)
    changed[number] = _with(snaps[number], labels=frozenset(labels))
    return changed, f"/oct {cmd.name} by {MAINTAINER}: {outcome.message}"


def _approved_560(snaps: Snaps) -> Snaps:
    """Projection: oct-support approves the current head of #560 (author with maintain/admin role)."""
    snap = snaps[560]
    review = Review("oct-support", "APPROVED", snap.head_sha, "NONE")
    return {**snaps, 560: _with(snap, author_permission="admin", reviews=(*snap.reviews, review))}


def _backfilled_537(snaps: Snaps) -> Snaps:
    """Projection: the backfill (MA-6) declares the legacy spec #537 (no DoR section, open PRs) ready."""
    snap = snaps[537]
    ready = frozenset({"phase:ready"})
    return {**snaps, 537: _with(snap, labels=snap.labels | ready, bot_phase_labels=ready)}


def _merged_560(snaps: Snaps) -> Snaps:
    """Projection: #560 squash-merged, GitHub retargets #570 onto main."""
    out = _approved_560(snaps)
    out[560] = _with(out[560], state="closed", merged=True)
    out[570] = _with(out[570], base_ref="main")
    return out


def _ladder(graph: Graph, cfg: Config) -> str:
    snap = graph.snapshots[573]
    found = detect(snap, graph.derived[573], graph, cfg, classify_actor(snap, cfg))
    v = next(v for v in found if v.rule == "V06")
    lines = [f"Level {level}: {format_notice(Notice(v, level), True)}" for level in (1, 2, 3)]
    issue = Violation("V02", 575, "someone", "The label `phase:in-progress` was added by hand.", "phase:in-progress")
    lines.append(f"Level 3 on an issue: {format_notice(Notice(issue, 3), False)}")
    return fence("\n\n".join(lines))


async def render_all() -> dict[str, str]:
    """Every snippet of the handbook by name."""
    cfg = _cfg()
    base = await recorded()
    now = graph_of(base, cfg)
    opened_573 = datetime(2026, 10, 26, 0, 58, tzinfo=timezone.utc)
    triaged, triage_line = await _command(base, 575, "/oct triage", cfg)
    after_triage = graph_of(triaged, cfg)
    approved = graph_of(_approved_560(base), cfg)
    merged = graph_of(_merged_560(base), cfg)
    backfilled = graph_of(_backfilled_537(base), cfg)
    out: dict[str, str] = {
        "498-labels": _labels(now, 498),
        "498-pinned": _guide(now, 498, cfg),
        "537-block": _block(now, 537, cfg),
        "537-labels": _labels(now, 537),
        "537-guide": _guide(now, 537, cfg),
        "560-block": _block(now, 560, cfg),
        "560-labels": _labels(now, 560),
        "560-guide": _guide(now, 560, cfg),
        "573-block": _block(now, 573, cfg),
        "573-labels": _labels(now, 573),
        "573-guide": _guide(now, 573, cfg, records=_violations(now, 573, cfg, opened_573)),
        "574-block": _block(now, 574, cfg),
        "574-labels": _labels(now, 574),
        "575-block": _block(now, 575, cfg),
        "575-labels": _labels(now, 575),
        "575-guide": _guide(now, 575, cfg),
        "575-triaged-labels": _labels(after_triage, 575),
        "575-triaged-guide": _guide(after_triage, 575, cfg, history=[triage_line]),
        "560-approved-block": _block(approved, 560, cfg),
        "560-approved-labels": _labels(approved, 560),
        "573-after-560-merged-block": _block(merged, 573, cfg),
        "537-backfilled-block": _block(backfilled, 537, cfg),
        "537-backfilled-labels": _labels(backfilled, 537),
        "573-backfilled-guide": _guide(backfilled, 573, cfg, records=_resolved(now, backfilled, 573, cfg, opened_573)),
        "ladder": _ladder(now, cfg),
    }
    return out


def extract(doc: str) -> dict[str, str]:
    """Snippets of a handbook text by name (the text between the marker lines)."""
    return {m[1]: m[2].removesuffix("\n") for m in _SNIPPET.finditer(doc)}


def replace(doc: str, snippets: dict[str, str]) -> str:
    """`doc` with every snippet replaced by its rendering in `snippets`."""

    def sub(match: re.Match[str]) -> str:
        text = snippets[match[1]]  # KeyError: the handbook names a snippet the renderer does not know
        return f"<!-- snippet:{match[1]} -->\n{text + chr(10) if text else ''}<!-- /snippet -->"

    return _SNIPPET.sub(sub, doc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", nargs="?", const=str(DOC), help="update the snippets of this handbook in place")
    args = parser.parse_args(argv)
    snippets = asyncio.run(render_all())
    if args.write:
        path = Path(args.write)
        path.write_text(replace(path.read_text(encoding="utf-8"), snippets), encoding="utf-8", newline="\n")
        return 0
    for name, text in snippets.items():
        sys.stdout.write(f"<!-- snippet:{name} -->\n{text}\n<!-- /snippet -->\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
