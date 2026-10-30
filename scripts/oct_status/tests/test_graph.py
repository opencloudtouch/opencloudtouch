from __future__ import annotations

import json
import re
from pathlib import Path

from oct_status.graph import build_graph, inverse, parse_prose_edges, walk_component
from oct_status.model import Edge, EdgeType
from tests.conftest import make_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(number: int) -> dict:
    return json.loads((FIXTURES / f"{number}.json").read_text(encoding="utf-8"))


def _pull(number: int) -> dict:
    return _fixture(number)[f"GET /repos/opencloudtouch/opencloudtouch/pulls/{number}"]


def test_part_of_and_closes():
    edges, unresolved = parse_prose_edges(7, "Part of #537\nCloses #531")
    assert Edge(EdgeType.IMPLEMENTS, 7, 537, "prose") in edges
    assert Edge(EdgeType.IMPLEMENTS, 7, 531, "prose") in edges
    assert unresolved == []


def test_part_of_in_real_fixture_body():
    edges, _ = parse_prose_edges(574, _pull(574)["body"])
    assert Edge(EdgeType.IMPLEMENTS, 574, 537, "prose") in edges


def test_depends_on_prose():
    edges, _ = parse_prose_edges(537, "Depends on #535")
    assert edges == [Edge(EdgeType.DEPENDS_ON, 537, 535, "prose")]
    assert inverse(edges[0]) == Edge(EdgeType.BLOCKS, 535, 537, "prose")


def test_unresolved_reference_is_listed():
    edges, unresolved = parse_prose_edges(7, "see the sleep timer spec")
    assert edges == [] and unresolved == []
    edges, unresolved = parse_prose_edges(7, "Part of #abc")
    assert edges == []
    assert unresolved == ["Part of #abc"]


def test_walk_component_respects_cap():
    async def neighbors(n: int) -> list[Edge]:
        return [Edge(EdgeType.RELATED, n, n + 1, "native")] if n < 40 else []

    import asyncio

    assert len(asyncio.run(walk_component(1, neighbors, 25))) == 25


def test_build_graph_emits_inverse_edges():
    snaps = {
        10: make_snapshot(number=10, is_pr=True, closing_refs=(5,)),
        5: make_snapshot(number=5, sub_issues=(6,), blocked_by=(4,)),
        6: make_snapshot(number=6),
        4: make_snapshot(number=4),
    }
    graph = build_graph(snaps)
    assert [e.target for e in graph.edges_of(10, EdgeType.IMPLEMENTS)] == [5]
    assert [e.target for e in graph.edges_of(5, EdgeType.IMPLEMENTED_BY)] == [10]
    assert [e.target for e in graph.edges_of(5, EdgeType.TRACKS)] == [6]
    assert [e.target for e in graph.edges_of(6, EdgeType.TRACKED_BY)] == [5]
    assert [e.target for e in graph.edges_of(5, EdgeType.DEPENDS_ON)] == [4]
    assert [e.target for e in graph.edges_of(4, EdgeType.BLOCKS)] == [5]
    assert all(e.origin == "native" for e in graph.edges)


def test_stack_edges_from_base_and_head_branches():
    p574, p573, p560 = _pull(574), _pull(573), _pull(560)
    # #570-#572 are taken from the GitHub API (not recorded as fixtures).
    chain = [
        (574, p574["base"]["ref"], p574["head"]["ref"]),
        (573, p573["base"]["ref"], p573["head"]["ref"]),
        (572, "feat/stream-recovery-backend", "feat/stream-recovery-frontend"),
        (571, "feat/device-settings-backend", "feat/stream-recovery-backend"),
        (570, "claude/gifted-bohr-b225kf", "feat/device-settings-backend"),
        (560, p560["base"]["ref"], p560["head"]["ref"]),
    ]
    assert chain[0][1:] == ("feat/sleep-timer-backend", "feat/sleep-timer-frontend")
    assert chain[1][1:] == ("feat/stream-recovery-frontend", "feat/sleep-timer-backend")
    assert chain[5][1:] == ("main", "claude/gifted-bohr-b225kf")
    snaps = {n: make_snapshot(number=n, is_pr=True, base_ref=b, head_ref=h) for n, b, h in chain}
    graph = build_graph(snaps)
    for upper, lower in [(574, 573), (573, 572), (572, 571), (571, 570), (570, 560)]:
        assert [e.target for e in graph.edges_of(upper, EdgeType.STACKED_ON)] == [lower]
        assert [e.target for e in graph.edges_of(lower, EdgeType.STACKED_BY)] == [upper]
    assert graph.edges_of(560, EdgeType.STACKED_ON) == []


def test_closed_pr_is_not_a_stack_parent():
    snaps = {
        1: make_snapshot(number=1, is_pr=True, state="closed", base_ref="main", head_ref="feat/x"),
        2: make_snapshot(number=2, is_pr=True, base_ref="feat/x", head_ref="feat/y"),
    }
    assert build_graph(snaps).edges_of(2, EdgeType.STACKED_ON) == []


def test_fork_pr_is_not_a_stack_parent():
    snaps = {
        1: make_snapshot(number=1, is_pr=True, base_ref="main", head_ref="main", head_is_fork=True),
        2: make_snapshot(number=2, is_pr=True, base_ref="main", head_ref="feat/y"),
    }
    graph = build_graph(snaps)
    assert graph.edges_of(2, EdgeType.STACKED_ON) == []
    assert graph.edges_of(1, EdgeType.STACKED_BY) == []


def test_native_edge_wins_over_prose():
    snaps = {
        10: make_snapshot(number=10, is_pr=True, body="Closes #5\nPart of #6", closing_refs=(5,)),
        5: make_snapshot(number=5),
    }
    graph = build_graph(snaps)
    to_5 = [e for e in graph.edges_of(10, EdgeType.IMPLEMENTS) if e.target == 5]
    assert to_5 == [Edge(EdgeType.IMPLEMENTS, 10, 5, "native")]
    assert [e.origin for e in graph.edges_of(5, EdgeType.IMPLEMENTED_BY)] == ["native"]
    to_6 = [e for e in graph.edges_of(10, EdgeType.IMPLEMENTS) if e.target == 6]
    assert to_6 == [Edge(EdgeType.IMPLEMENTS, 10, 6, "prose")]


def test_fixtures_are_sanitized():
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 7
    ipv4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not ipv4.search(text), path.name
        assert not email.search(text), path.name
        for marker in ("ghp_", "github_pat_", "Bearer "):
            assert marker not in text, (path.name, marker)
        assert "http" not in text, path.name


def test_closes_list_yields_one_edge_per_target():
    edges, _ = parse_prose_edges(9, "Closes #1, #2 and #3")
    assert [e.target for e in edges] == [1, 2, 3]


def test_capture_sanitizer_drops_free_text():
    from oct_status.tools.capture_fixture import sanitize_body, sanitize_checks

    body = "Call 10.0.0.5 or mail a@b.de\nPart of #537 please\nsecret text\nsee #12 now"
    assert sanitize_body(body) == "Part of #537\nSee #12"
    checks = sanitize_checks(
        {
            "check_runs": [
                {
                    "name": "x",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"slug": "gha"},
                    "html_url": "http://u",
                }
            ]
        }
    )
    assert checks["check_runs"] == [
        {"name": "x", "status": "completed", "conclusion": "success", "app": {"slug": "gha"}}
    ]
