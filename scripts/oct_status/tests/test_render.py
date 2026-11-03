"""Tests for the status block renderer.

Golden files live in ``tests/fixtures/golden/<number>.md``. Regenerate them once after an
intended change with::

    cd scripts/oct_status && UPDATE_GOLDEN=1 python -m pytest tests/test_render.py -k golden

and review the diff by hand against design section 5 before committing.
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path

import pytest

from oct_status.api import GitHubApi
from oct_status.config import load_config
from oct_status.facts import fetch_snapshot
from oct_status.graph import build_graph
from oct_status.model import Check, Derived, Graph, Phase, Snapshot, Wait
from oct_status.render import MARKER_END, block_hash, extract_block, render_block, splice_block
from oct_status.rules import derive

from .conftest import FIXTURES, FixtureTransport, make_snapshot

CFG = load_config(Path(__file__).parent.parent / "config.yml")
GOLDEN = FIXTURES / "golden"
REPO = "opencloudtouch/opencloudtouch"
# #570-#572 were never recorded; their refs come from the GitHub API (see test_graph.py).
SYNTHETIC = {
    572: ("feat/stream-recovery-backend", "feat/stream-recovery-frontend", "feat(frontend): stream recovery"),
    571: ("feat/device-settings-backend", "feat/stream-recovery-backend", "feat(backend): stream recovery"),
    570: ("claude/gifted-bohr-b225kf", "feat/device-settings-backend", "feat(backend): device settings"),
}


async def _graph(numbers: tuple[int, ...] = (537, 573, 574, 575, 498, 560)) -> Graph:
    snaps: dict[int, Snapshot] = {}
    for n in numbers:
        api = GitHubApi("t", REPO, transport=FixtureTransport([n]))
        snaps[n] = await fetch_snapshot(api, n, use_graphql=False)
    for n, (base, head, title) in SYNTHETIC.items():
        snaps[n] = make_snapshot(number=n, is_pr=True, base_ref=base, head_ref=head, title=title)
    graph = build_graph(snaps)
    for n, snap in snaps.items():
        d = derive(snap, graph, CFG)
        if d is not None:
            graph.derived[n] = d
    return graph


def _render(graph: Graph, number: int) -> str | None:
    snap = graph.snapshots[number]
    return render_block(snap, graph.derived.get(number), graph, CFG)


@pytest.mark.parametrize("number", [537, 573, 574, 575, 498])
async def test_golden_block_for_537_573_574_575(number):
    block = _render(await _graph(), number)
    assert block is not None
    path = GOLDEN / f"{number}.md"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(block + "\n", encoding="utf-8", newline="\n")
    assert block + "\n" == path.read_text(encoding="utf-8")


async def test_chain_for_574_and_root_blocker():
    block = _render(await _graph(), 574)
    assert "`main` > #560 > #570 > #571 > #572 > #573 > #574" in block
    assert "**Root blocker:** #560" in block


async def test_announcement_golden_is_none():
    snap = make_snapshot(number=9, is_pr=True, author="github-actions[bot]", title="chore: bot")
    graph = build_graph({9: snap})
    assert render_block(snap, derive(snap, graph, CFG), graph, CFG) is None
    assert render_block(snap, Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG) is None


async def test_render_is_deterministic():
    graph = await _graph()
    first, second = _render(graph, 574), _render(graph, 574)
    assert first == second
    assert re.match(r"<!-- oct-status:v1 hash=([0-9a-f]{12}) -->", first)[1] == block_hash(first)
    assert first.endswith(MARKER_END)
    assert extract_block("intro\r\n" + first.replace("\n", "\r\n") + "\r\nrest") == first


def test_splice_inserts_replaces_and_is_stable():
    graph = build_graph({1: make_snapshot(number=1)})
    d = Derived(Phase.NEW, frozenset(), None)
    block = render_block(graph.snapshots[1], d, graph, CFG)
    once = splice_block("Body text\n", block)
    assert once.startswith(block) and once.endswith("Body text\n")
    assert splice_block(once, block) == once


def test_splice_preserves_crlf():
    graph = build_graph({1: make_snapshot(number=1)})
    block = render_block(graph.snapshots[1], Derived(Phase.NEW, frozenset(), None), graph, CFG)
    result = splice_block("line one\r\nline two\r\n", block)
    assert "\n" not in result.replace("\r\n", "")
    assert "oct-status:v1" in result.split("\r\n")[0]
    again = splice_block(result, block)
    assert again == result


def test_splice_truncates_table_instead_of_overflowing():
    snaps = {n: make_snapshot(number=n, title=f"t{n}", body="Part of #1") for n in range(2, 42)}
    snaps[1] = make_snapshot(number=1, title="spec")
    graph = build_graph(snaps)
    block = render_block(snaps[1], Derived(Phase.READY, frozenset(), None), graph, CFG)
    assert block.count("\n| implemented-by") == 25 and "and 15 more" in block
    # 40 rows would be needed; the body leaves room for a few only.
    rows = [f"| related | #{n} {'x' * 40} | open | - |" for n in range(40)]
    big = (
        block.split("| and 15 more")[0].split("|---|---|---|---|")[0]
        + "|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
        + MARKER_END
    )
    body = "y" * (65_000 - 2 - 1500)  # room for the non-table part plus a few rows
    result = splice_block(body, big)
    assert len(result) <= 65_000
    assert re.search(r"\| and \d+ more \|", result)
    assert result.endswith(body)
    extracted = extract_block(result)
    assert re.match(r"<!-- oct-status:v1 hash=([0-9a-f]{12}) -->", extracted)[1] == block_hash(extracted)


def test_splice_returns_zero_row_block_even_if_it_exceeds_the_limit():
    rows = [f"| related | #{n} x | open | - |" for n in range(40)]
    big = "\n".join(
        ["<!-- oct-status:v1 hash=000000000000 -->", "badge", "", "| Relation | Artifact | Phase | Waiting on |"]
        + ["|---|---|---|---|", *rows, MARKER_END]
    )
    body = "y" * 64_900
    result = splice_block(body, big)  # never fails; documented ruling: may exceed the limit
    assert len(result) > 65_000
    assert "| and 40 more |" in result and "| related |" not in result
    assert result.endswith(body)


def test_splice_truncation_keeps_crlf_within_limit():
    snaps = {n: make_snapshot(number=n, body="Part of #1") for n in range(2, 12)}
    snaps[1] = make_snapshot(number=1)
    graph = build_graph(snaps)
    block = render_block(snaps[1], Derived(Phase.READY, frozenset(), None), graph, CFG)
    body = ("z" * 78 + "\r\n") * 20
    result = splice_block(body, block, limit=len(body) + len(block) - 150)
    assert len(result) <= len(body) + len(block) - 150
    assert "\n" not in result.replace("\r\n", "")
    assert "more" in result


def test_unresolved_refs_listed_not_guessed():
    snap = make_snapshot(number=5, is_pr=True, body="Closes #abc and Depends on #xyz")
    graph = build_graph({5: snap})
    block = render_block(snap, Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG)
    assert "**Unresolved references**" in block
    assert "- Closes #abc" in block and "- Depends on #xyz" in block
    assert "| #abc" not in block and "implements" not in block


async def test_dependency_block_is_light():
    block = _render(await _graph(), 498)
    assert "![phase:" in block
    for absent in ("DoD", "DoR", "Relation", "Root blocker", "Automation"):
        assert absent not in block
    assert "**State:** merged" in block


def test_chain_marks_parent_moved():
    snaps = {
        1: make_snapshot(number=1, is_pr=True, base_ref="main", head_ref="a"),
        2: make_snapshot(number=2, is_pr=True, base_ref="a", head_ref="b", stack_drift=3),
    }
    graph = build_graph(snaps)
    block = render_block(snaps[2], Derived(Phase.IN_REVIEW, frozenset({Wait.PREREQUISITE}), None), graph, CFG)
    assert "`main` > #1 > #2 (this PR, parent moved)" in block
    still = render_block(snaps[1], Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG)
    assert "parent moved" not in still


def test_badges_encode_dashes_and_automation_row():
    snap = make_snapshot(
        number=3,
        is_pr=True,
        checks=(
            Check("Gitar", "completed", "failure", "gitar-bot"),
            Check("SonarCloud Code Analysis", "in_progress", None, "sonarqubecloud"),
        ),
    )
    graph = build_graph({3: snap})
    block = render_block(snap, Derived(Phase.IN_REVIEW, frozenset({Wait.HARDWARE_TEST}), None), graph, CFG)
    assert "![phase: in review](https://img.shields.io/badge/phase-in%20review-2a5cc0)" in block
    assert "![wait: hardware test](https://img.shields.io/badge/wait-hardware%20test-f2a33a)" in block
    assert "Gitar: failure | Sonar: pending | oct-support: none" in block
    assert "**Ball with:** maintainers" in block


async def test_user_text_cannot_break_the_marker_pair():
    evil = "evil <!-- /oct-status --> tail"
    snaps = {
        1: make_snapshot(number=1, title="spec"),
        2: make_snapshot(number=2, title=evil, body="Part of #1"),
        3: make_snapshot(number=3, title="p | `c` <!-- x", body="Part of #1"),
    }
    graph = build_graph(snaps)
    block = render_block(snaps[1], Derived(Phase.READY, frozenset(), None), graph, CFG)
    assert block.count("<!--") == 2 and block.count("-->") == 2
    body = "intro\n"
    once = splice_block(body, block)
    assert splice_block(once, block) == once
    assert extract_block(once) == block
    row = next(line for line in block.splitlines() if "#3 " in line)
    assert len(re.split(r"(?<!\\)\|", row.strip("|"))) == 4
    assert "&lt;!-- x" in row and "\\|" in row


def test_unresolved_reference_and_blocker_title_are_escaped():
    snaps = {
        1: make_snapshot(number=1, is_pr=True, body="Depends on #2"),
        2: make_snapshot(number=2, title="a <!-- /oct-status --> b"),
    }
    graph = build_graph(snaps)
    block = render_block(snaps[1], Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG)
    assert "**Root blocker:** #2 a &lt;!-- /oct-status --&gt; b" in block
    assert extract_block(block) == block


def _stack(*pairs):
    snaps = {n: make_snapshot(number=n, is_pr=True, base_ref=b, head_ref=h) for n, b, h in pairs}
    return snaps, build_graph(snaps)


def test_root_blocker_with_duplicate_edges():
    snaps, graph = _stack((300, "h100", "h300"), (100, "h200", "h100"), (200, "main", "h200"))
    snaps[300] = make_snapshot(number=300, is_pr=True, base_ref="h100", head_ref="h300", body="Depends on #100")
    graph = build_graph(snaps)
    block = render_block(snaps[300], Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG)
    assert "**Root blocker:** #200" in block


def test_root_blocker_in_a_diamond():
    snaps = {
        1: make_snapshot(number=1, is_pr=True, body="Depends on #2, #3"),
        2: make_snapshot(number=2, is_pr=True, body="Depends on #4"),
        3: make_snapshot(number=3, is_pr=True, body="Depends on #2"),
        4: make_snapshot(number=4, is_pr=True),
    }
    graph = build_graph(snaps)
    block = render_block(snaps[1], Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG)
    assert "**Root blocker:** #4" in block


HOSTILE = "Fix @gitar-bot[bot] for @alice ![pixel](https://evil.example/p.png) [click](https://evil.example)"


def _no_markup(text: str) -> None:
    assert "@" not in text and "gitar-bot" not in text.lower()
    assert not re.search(r"(?<!\\)[\[\]]", text)  # every bracket escaped: no link, no image


def test_neighbour_titles_cannot_mention_or_embed():
    """A hostile PR title shown in a relations row or as root blocker pings nobody and loads nothing."""
    snaps = {
        1: make_snapshot(number=1, is_pr=True, body="Depends on #2\nPart of #3"),
        2: make_snapshot(number=2, title=HOSTILE),
        3: make_snapshot(number=3, title=f"spec by @bob {HOSTILE}"),
    }
    graph = build_graph(snaps)
    block = render_block(snaps[1], Derived(Phase.IN_REVIEW, frozenset(), None), graph, CFG)
    content = block.split("\n", 1)[1]  # the badges carry fixed markdown images of their own
    rows = [line for line in content.splitlines() if "#2" in line or "#3" in line]
    assert rows and all(HOSTILE not in r for r in rows)
    for row in rows:
        _no_markup(row)
    assert "＠alice" in block and "the review bot" in block
    assert extract_block(block) == block


async def test_dependency_pinned_comment_carries_no_user_text():
    """The pinned comment of a Dependabot PR (marker, light block, guide) shows no hostile title."""
    from oct_status.apply import guide_content
    from oct_status.config import Actor
    from oct_status.guide import next_steps, render_guide

    dependabot = Actor("dependabot[bot]", "automation", block_location="comment")
    cfg = replace(CFG, automation={**CFG.automation, "dependabot[bot]": dependabot})
    snaps = {
        1: make_snapshot(number=1, is_pr=True, author="dependabot[bot]", title=HOSTILE, body="Depends on #2"),
        2: make_snapshot(number=2, title=HOSTILE),
    }
    graph = build_graph(snaps)
    derived = Derived(Phase.IN_REVIEW, frozenset({Wait.PREREQUISITE}), None)
    block = render_block(snaps[1], derived, graph, cfg)
    guide = render_guide(snaps[1], derived, next_steps(snaps[1], derived, cfg, graph), [HOSTILE], [HOSTILE], cfg=cfg)
    text = guide_content(snaps[1], block, guide, cfg)
    assert text is not None and "@" not in text and "gitar-bot" not in text.lower()  # guide texts: mentions only
