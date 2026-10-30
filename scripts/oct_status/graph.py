"""Relation graph between issues and pull requests.

Native GitHub relations (closing references, sub-issues, blocked-by, stacked branches)
win over relations parsed from prose. Every edge is emitted together with its inverse
because ``Graph.edges_of`` only matches on the source.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Awaitable, Callable

from .model import Edge, EdgeType, Graph, Snapshot

_INVERSE_PAIRS = (
    (EdgeType.IMPLEMENTS, EdgeType.IMPLEMENTED_BY),
    (EdgeType.STACKED_ON, EdgeType.STACKED_BY),
    (EdgeType.DEPENDS_ON, EdgeType.BLOCKS),
    (EdgeType.VERIFIES, EdgeType.VERIFIED_BY),
    (EdgeType.SPECIFIED_BY, EdgeType.SPECIFIES),
    (EdgeType.ORIGIN, EdgeType.SPAWNED),
    (EdgeType.TRACKS, EdgeType.TRACKED_BY),
    (EdgeType.SUPERSEDED_BY, EdgeType.SUPERSEDES),
)
_INVERSE: dict[EdgeType, EdgeType] = {}
for _a, _b in _INVERSE_PAIRS:
    _INVERSE[_a] = _b
    _INVERSE[_b] = _a
# Symmetric types are their own inverse.
_INVERSE[EdgeType.RELATED] = EdgeType.RELATED
_INVERSE[EdgeType.FOLLOW_UP] = EdgeType.FOLLOW_UP

# Edge types along which the event fan-out propagates (ruling M4): the derived state at the other end
# depends on this artifact. `tracked-by` goes up to a tracking issue, whose phase follows its children;
# `tracks` is left out, so a walk never comes back down to the siblings. `verifies` carries a closed
# test plan to its target. Display-only relations (origin, supersedes, related, follow-up) are healed
# by the daily audit.
PROPAGATING = frozenset(
    {
        EdgeType.IMPLEMENTS,
        EdgeType.IMPLEMENTED_BY,
        EdgeType.STACKED_ON,
        EdgeType.STACKED_BY,
        EdgeType.DEPENDS_ON,
        EdgeType.BLOCKS,
        EdgeType.SPECIFIED_BY,
        EdgeType.SPECIFIES,
        EdgeType.VERIFIES,
        EdgeType.TRACKED_BY,
    }
)

_PROSE_TYPES = {
    "closes": EdgeType.IMPLEMENTS,
    "part of": EdgeType.IMPLEMENTS,
    "depends on": EdgeType.DEPENDS_ON,
}
_PROSE = re.compile(r"\b(closes|part of|depends on)\s+#(\w+)", re.IGNORECASE)
_CONTINUATION = re.compile(r"\s*(?:,|and)\s*#(\d+)", re.IGNORECASE)


def inverse(edge: Edge) -> Edge:
    """The same relation seen from the other side; origin is kept."""
    return Edge(_INVERSE[edge.type], edge.target, edge.source, edge.origin)


def parse_prose_edges(number: int, body: str) -> tuple[list[Edge], list[str]]:
    """Edges from ``Closes``/``Part of``/``Depends on`` phrases plus unresolved references."""
    edges: list[Edge] = []
    unresolved: list[str] = []
    for match in _PROSE.finditer(body or ""):
        keyword, ref = match.group(1), match.group(2)
        if not ref.isdigit():
            unresolved.append(f"{keyword} #{ref}")
            continue
        edge_type = _PROSE_TYPES[keyword.lower()]
        targets = [int(ref)]
        rest = body[match.end() :]
        while (cont := _CONTINUATION.match(rest)) is not None:
            targets.append(int(cont.group(1)))
            rest = rest[cont.end() :]
        for target in targets:
            edge = Edge(edge_type, number, target, "prose")
            if edge not in edges:
                edges.append(edge)
    return edges, unresolved


async def walk_component(
    start: int,
    neighbors: Callable[[int], Awaitable[list[Edge]]],
    cap: int,
) -> set[int]:
    """Breadth-first walk over edges, returning at most `cap` nodes (including `start`)."""
    seen: set[int] = {start}
    queue: deque[int] = deque([start])
    while queue and len(seen) < cap:
        node = queue.popleft()
        for edge in await neighbors(node):
            if edge.target not in seen and len(seen) < cap:
                seen.add(edge.target)
                queue.append(edge.target)
    return seen


def _native_edges(snapshots: dict[int, Snapshot]) -> list[Edge]:
    edges: list[Edge] = []
    for number, snap in snapshots.items():
        edges += [Edge(EdgeType.IMPLEMENTS, number, t, "native") for t in snap.closing_refs]
        edges += [Edge(EdgeType.TRACKS, number, t, "native") for t in snap.sub_issues]
        edges += [Edge(EdgeType.DEPENDS_ON, number, t, "native") for t in snap.blocked_by]
    heads: dict[str, list[int]] = {}
    for number, snap in snapshots.items():
        if snap.is_pr and snap.head_ref and snap.state == "open" and not snap.head_is_fork:
            heads.setdefault(snap.head_ref, []).append(number)
    for number, snap in snapshots.items():
        if snap.is_pr and snap.base_ref:
            edges += [
                Edge(EdgeType.STACKED_ON, number, below, "native")
                for below in heads.get(snap.base_ref, [])
                if below != number
            ]
    return edges


def build_graph(snapshots: dict[int, Snapshot]) -> Graph:
    """Build the relation graph; native edges win over identical prose edges."""
    edges: list[Edge] = []
    seen: set[tuple[EdgeType, int, int]] = set()

    def add(edge: Edge) -> None:
        for e in (edge, inverse(edge)):
            key = (e.type, e.source, e.target)
            if key not in seen:
                seen.add(key)
                edges.append(e)

    for edge in _native_edges(snapshots):
        add(edge)
    for number, snap in snapshots.items():
        for edge in parse_prose_edges(number, snap.body)[0]:
            add(edge)
    return Graph(edges=edges, snapshots=snapshots, derived={})
