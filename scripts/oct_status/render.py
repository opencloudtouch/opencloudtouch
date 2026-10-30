"""Status block rendering and splicing (design section 5).

The block is a pure projection of the derived state: deterministic, no clock, no I/O except the
one-time read of ``labels.yml`` for phase colours. ``splice_block`` keeps the body's line endings
and shortens the relations table, never the rest of the body, when the size limit is hit.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import yaml

from .config import Config
from .graph import parse_prose_edges
from .model import Derived, Edge, EdgeType, Graph, Kind, Snapshot, Wait
from .rules import OCT_SUPPORT, detect_kind

MARKER_END = "<!-- /oct-status -->"
TABLE_CAP = 25
WAIT_COLOR = "f2a33a"
NEUTRAL_COLOR = "6e7781"
_START = re.compile(r"<!-- oct-status:v1 hash=([0-9a-f]{12}) -->")
_BLOCK = re.compile(r"<!-- oct-status:v1 hash=[0-9a-f]{12} -->.*?<!-- /oct-status -->", re.DOTALL)
_MORE = re.compile(r"^\| and (\d+) more \|")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_ITEM = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s*(.*?)\s*$")
_ROLE = {  # wait -> who has to act
    Wait.MAINTAINER: "maintainers",
    Wait.REPORTER: "reporter",
    Wait.FINDINGS: "author",
    Wait.CI: "author",
    Wait.SPEC_FIX: "author",
    Wait.PREREQUISITE: "author",
    Wait.HARDWARE_TEST: "maintainers",
    Wait.DESIGNER: "designer",
}
_ISSUE_BALL = {"new": "maintainers", "draft": "author", "spec-rework": "author", "spec-review": "reviewer"}


@lru_cache(maxsize=1)
def _phase_colors() -> dict[str, str]:
    raw = yaml.safe_load((Path(__file__).parent / "labels.yml").read_text(encoding="utf-8"))
    return {e["name"]: str(e["color"]) for e in raw["labels"]}


def badge(label: str, message: str, color: str) -> str:
    """Static Shields.io badge; alt text repeats the content for readers without images."""

    def esc(text: str) -> str:
        return quote(text.replace("-", "--").replace("_", "__"), safe="")

    return f"![{label}: {message}](https://img.shields.io/badge/{esc(label)}-{esc(message)}-{color})"


def block_hash(block: str) -> str:
    """First 12 hex digits of SHA-256 over everything after the marker line."""
    content = block.replace("\r\n", "\n").split("\n", 1)[1] if "\n" in block else ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def neutralise(text: str) -> str:
    """Escape ``&``, ``<`` and ``>`` so user text can never open or close an HTML comment."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cell(text: str) -> str:
    return neutralise(" ".join(text.split())).replace("|", "\\|")


def _is_open(graph: Graph, number: int) -> bool:
    snap = graph.snapshots.get(number)
    return snap is None or (snap.state == "open" and not snap.merged)


def _root_blocker(snap: Snapshot, graph: Graph) -> int | None:
    seen: set[int] = {snap.number}
    leaves: list[int] = []
    stack = [snap.number]
    while stack:
        current = stack.pop()
        blockers = [
            e.target
            for t in (EdgeType.STACKED_ON, EdgeType.DEPENDS_ON)
            for e in graph.edges_of(current, t)
            if _is_open(graph, e.target)
        ]
        fresh = [b for b in blockers if b not in seen]
        seen.update(fresh)
        stack.extend(fresh)
        # A leaf has no open blocker at all; `seen` only guards the traversal against cycles.
        if not blockers and current != snap.number:
            leaves.append(current)
    return min(leaves) if leaves else None


def _stack_chain(snap: Snapshot, graph: Graph) -> str | None:
    def walk(edge_type: EdgeType) -> list[int]:
        seen, current = {snap.number}, snap.number
        out: list[int] = []
        while True:
            nxt = [e.target for e in graph.edges_of(current, edge_type) if e.target not in seen]
            if not nxt:
                return out
            current = nxt[0]
            seen.add(current)
            out.append(current)

    below, above = walk(EdgeType.STACKED_ON), walk(EdgeType.STACKED_BY)
    if not below and not above:
        return None
    root = graph.snapshots.get(below[-1]) if below else snap
    parts = [f"`{neutralise((root.base_ref if root else '') or 'main')}`"] + [f"#{n}" for n in reversed(below)]
    mark = "this PR, parent moved" if (snap.stack_drift or 0) > 0 else "this PR"
    parts.append(f"#{snap.number} ({mark})")
    parts += [f"#{n}" for n in above]
    return " > ".join(parts)


def _check(snap: Snapshot, name: str) -> str:
    for check in snap.checks:
        if check.name == name:
            return check.conclusion if check.status == "completed" and check.conclusion else "pending"
    return "none"


def _automation(snap: Snapshot) -> str:
    verdicts = [r.state for r in snap.reviews if r.user == OCT_SUPPORT]
    review = verdicts[-1].lower().replace("_", " ") if verdicts else "none"
    return f"Gitar: {_check(snap, 'Gitar')} | Sonar: {_check(snap, 'SonarCloud Code Analysis')} | oct-support: {review}"


def _ball(snap: Snapshot, derived: Derived) -> str:
    roles = {_ROLE[w] for w in derived.waits}
    if not roles and not snap.merged and snap.state == "open":
        if snap.is_pr:
            roles = {"author"} if snap.draft else {"maintainers"}
        elif derived.phase.value in _ISSUE_BALL:
            roles = {_ISSUE_BALL[derived.phase.value]}
    return ", ".join(sorted(roles)) or "nobody"


def _checklist(body: str, heading: str) -> tuple[int, int] | None:
    lines, level, start = (body or "").splitlines(), 0, 0
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and len(match[1]) in (2, 3) and match[2].lower().startswith(heading):
            level, start = len(match[1]), index + 1
            break
    if not level:
        return None
    done = total = 0
    for line in lines[start:]:
        head = _HEADING.match(line)
        if head and len(head[1]) <= level:
            break
        item = _ITEM.match(line)
        if item:
            total += 1
            done += item[1] != " " or bool(re.search(r"\bn/a\b", item[2], re.IGNORECASE))
    return (done, total) if total else None


def _counters(snap: Snapshot, kind: Kind, graph: Graph) -> list[str]:
    out: list[str] = []
    parts = sorted({e.target for e in graph.edges_of(snap.number, EdgeType.IMPLEMENTED_BY)})
    if kind == Kind.SPEC and parts:
        merged = sum(1 for p in parts if _part_done(graph, p))
        out.append(badge("Parts", f"{merged}/{len(parts)}", NEUTRAL_COLOR))
    checklist = _checklist(snap.body, "definition of done" if snap.is_pr else "definition of ready")
    if checklist:
        out.append(badge("DoD" if snap.is_pr else "DoR", f"{checklist[0]}/{checklist[1]}", NEUTRAL_COLOR))
    return out


def _part_done(graph: Graph, number: int) -> bool:
    derived, snap = graph.derived.get(number), graph.snapshots.get(number)
    if derived is not None:
        return derived.phase.value in ("merged", "done")
    return bool(snap and snap.merged)


def _badges(derived: Derived) -> list[str]:
    phase = derived.phase.value.replace("-", " ")
    out = [badge("phase", phase, _phase_colors().get(derived.phase.label, NEUTRAL_COLOR))]
    out += [badge("wait", w.value.replace("-", " "), WAIT_COLOR) for w in sorted(derived.waits)]
    if derived.resolution:
        out.append(badge("resolution", derived.resolution.value.replace("-", " "), NEUTRAL_COLOR))
    return out


def _relation_rows(snap: Snapshot, graph: Graph) -> list[str]:
    order = list(EdgeType)
    edges: list[Edge] = sorted(
        {(e.type, e.target): e for e in graph.edges_of(snap.number)}.values(),
        key=lambda e: (order.index(e.type), e.target),
    )
    rows = []
    for edge in edges:
        other, derived = graph.snapshots.get(edge.target), graph.derived.get(edge.target)
        title = f" {_cell(other.title)}" if other and other.title else ""
        phase = derived.phase.value if derived else "-"
        waits = ", ".join(sorted(w.value for w in derived.waits)) if derived and derived.waits else "-"
        rows.append(f"| {edge.type.value} | #{edge.target}{title} | {phase} | {waits} |")
    return rows


def _table(rows: list[str], extra: int = 0) -> list[str]:
    if not rows and not extra:
        return []
    lines = ["| Relation | Artifact | Phase | Waiting on |", "|---|---|---|---|", *rows]
    if extra:
        lines.append(f"| and {extra} more | | | |")
    return lines


def _wrap(content: list[str]) -> str:
    while content and not content[-1]:
        content = content[:-1]
    body = "\n".join([*content, MARKER_END])
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    return f"<!-- oct-status:v1 hash={digest} -->\n{body}"


def render_block(snap: Snapshot, derived: Derived | None, graph: Graph, cfg: Config) -> str | None:
    """Status block for one artifact, or ``None`` for announcements (no block is ever written)."""
    kind = detect_kind(snap, cfg)
    if derived is None or kind == Kind.ANNOUNCEMENT:
        return None
    if kind == Kind.DEPENDENCY_PR:
        state = "merged" if snap.merged else snap.state
        return _wrap([" ".join(_badges(derived)), "", f"**State:** {state}{' (draft)' if snap.draft else ''}"])
    content = [" ".join([*_badges(derived), *_counters(snap, kind, graph)]), ""]
    blocker = _root_blocker(snap, graph)
    other = graph.snapshots.get(blocker) if blocker else None
    label = f"#{blocker}{f' {_cell(other.title)}' if other and other.title else ''}" if blocker else "none"
    content += [f"**Root blocker:** {label}", ""]
    chain = _stack_chain(snap, graph) if snap.is_pr else None
    if chain:
        content += [f"**Stack:** {chain}", ""]
    if snap.is_pr:
        # Known gap: Gitar's risk and auto-apply state live in its dashboard comment, which
        # facts.py does not fetch yet; only check conclusions and the oct-support review show here.
        content += [f"**Automation:** {_automation(snap)}", ""]
    content += [f"**Ball with:** {_ball(snap, derived)}", ""]
    rows = _relation_rows(snap, graph)
    content += _table(rows[:TABLE_CAP], max(0, len(rows) - TABLE_CAP))
    unresolved = parse_prose_edges(snap.number, snap.body)[1]
    if unresolved:
        content += ["", "**Unresolved references**", "", *[f"- {_cell(u)}" for u in unresolved]]
    return _wrap(content)


def extract_block(body: str) -> str | None:
    """The block inside `body` (newlines normalised to ``\\n``), or ``None``."""
    match = _BLOCK.search((body or "").replace("\r\n", "\n"))
    return match.group(0) if match else None


def _shrink(block: str, limit_chars: int, eol: str) -> str:
    lines = block.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.startswith("|---")), None)
    if first is None:
        return block
    start = first + 1
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    rows = lines[start:end]
    extra = 0
    if rows and (m := _MORE.match(rows[-1])):
        extra, rows = int(m[1]), rows[:-1]
    keep = len(rows)
    while True:
        dropped = len(rows) - keep + extra
        more = [f"| and {dropped} more | | | |"] if dropped else []
        candidate = _wrap([*lines[1:start], *rows[:keep], *more, *lines[end:-1]])
        if len(candidate.replace("\n", eol)) <= limit_chars or keep == 0:
            return candidate
        keep -= 1


def splice_block(body: str, block: str, limit: int = 65_000) -> str:
    """Put `block` at the top of `body`, replacing an existing one, within `limit` characters.

    Only the relations table is shortened. If the block without any table row still does not fit,
    it is returned anyway (never fails) and the result may exceed `limit`.
    """
    eol = "\r\n" if "\r\n" in body else "\n"
    rest = _BLOCK.sub("", body.replace("\r\n", "\n"), count=1).lstrip("\n")
    block = block.replace("\r\n", "\n")
    tail = "\n\n" + rest if rest else ""
    room = limit - len(tail.replace("\n", eol))
    if len(block.replace("\n", eol)) > room:
        block = _shrink(block, room, eol)
    return (block + tail).replace("\n", eol)
