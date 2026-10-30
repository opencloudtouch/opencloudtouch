"""Tests for next steps and the guide comment."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from oct_status.config import load_config
from oct_status.guide import Step, next_steps, render_guide
from oct_status.model import Derived, Phase, Wait

from .conftest import make_snapshot

CFG = load_config(Path(__file__).parent.parent / "config.yml")
DOR_OPEN = "## Definition of Ready\n\n- [x] Goal\n- [ ] Acceptance criteria\n"
DOR_DONE = "## Definition of Ready\n\n- [x] Goal\n- [x] Acceptance criteria\n"


def _commands(steps):
    return [s.command for s in steps]


@pytest.mark.parametrize(
    ("snap_kwargs", "phase", "waits", "expect_cmd", "expect_text"),
    [
        ({"is_pr": True}, Phase.IN_REVIEW, {Wait.MAINTAINER}, "/oct approve", None),
        ({"is_pr": True, "unresolved_threads": 3}, Phase.IN_REVIEW, {Wait.FINDINGS}, None, "3 open review threads"),
        ({"is_pr": True}, Phase.MERGED, {Wait.HARDWARE_TEST}, "/oct verified <device or note>", None),
        (
            {"is_pr": True, "base_ref": "feat/x"},
            Phase.IN_REVIEW,
            {Wait.PREREQUISITE},
            None,
            "stack parent branch `feat/x`",
        ),
        ({"labels": frozenset({"spec"}), "body": DOR_OPEN}, Phase.DRAFT, set(), None, "Acceptance criteria"),
        ({"labels": frozenset({"spec"}), "body": DOR_DONE}, Phase.DRAFT, set(), "/oct review", None),
        (
            {"labels": frozenset({"spec"}), "body": DOR_DONE},
            Phase.SPEC_REVIEW,
            set(),
            '/oct ready --reviewer <login or "independent-review">',
            None,
        ),
    ],
)
def test_next_steps_per_state(snap_kwargs, phase, waits, expect_cmd, expect_text):
    snap = make_snapshot(**snap_kwargs)
    steps = next_steps(snap, Derived(phase, frozenset(waits), None), CFG)
    assert steps and len(steps) <= 5
    if expect_cmd:
        assert expect_cmd in _commands(steps)
    if expect_text:
        assert any(expect_text in s.text for s in steps)
    if "Acceptance criteria" == expect_text:
        assert "/oct review" not in _commands(steps)
        assert all(s.command is None for s in steps)


def test_next_steps_never_more_than_five():
    snap = make_snapshot(is_pr=True)
    steps = next_steps(snap, Derived(Phase.IN_REVIEW, frozenset(Wait), None), CFG)
    assert len(steps) == 5


def _guide(**kw):
    snap = make_snapshot(is_pr=True)
    derived = Derived(Phase.IN_REVIEW, frozenset({Wait.MAINTAINER}), None)
    steps = next_steps(snap, derived, CFG)
    args = {
        "notices": ["V07 something", "[resolved] V03 fixed"],
        "history": ["set wait:maintainer", "a", "b", "c", "d", "e"],
    }
    args.update(kw)
    return render_guide(snap, derived, steps, args["notices"], args["history"])


def test_guide_sections_and_data_block():
    text = _guide()
    assert text.startswith("<!-- oct-next:v1 -->")
    titles = [
        "### Last action",
        "### You are here",
        "### Next steps",
        "### Commands valid now",
        "### Notices",
        "### History",
    ]
    positions = [text.index(t) for t in titles]
    assert positions == sorted(positions)
    assert "set wait:maintainer" in text.split("### You are here")[0]
    assert text.index("Resolved notices (1)") > text.index("### Notices")
    assert "<details>" in text.split("### History")[1]
    assert text.split("### History")[1].count("\n- ") == 5
    data = json.loads(re.search(r"<!-- oct-next-data (.*) -->", text)[1])
    assert data["phase"] == "in-review" and data["waits"] == ["maintainer"]
    assert data["next"][0] == {"actor": "author", "command": "/oct approve", "text": data["next"][0]["text"]}
    assert "- `/oct approve`" in text


def test_guide_without_history_and_steps():
    snap = make_snapshot()
    text = render_guide(snap, Derived(Phase.DONE, frozenset(), None), [], [], [])
    assert "### Last action\n\n-\n" in text and "Nothing to do." in text


def test_guide_never_starts_with_gitar():
    text = _guide(history=["Gitar found 3 issues", "ping @gitar-bot"], notices=["gitar-bot[bot] pushed"])
    assert not text.lower().lstrip().startswith("gitar")
    assert "gitar-bot" not in text.lower()
    for line in text.splitlines():
        stripped = re.sub(r"^[-\d.\s*]+", "", line).lstrip().lower()
        assert not stripped.startswith("gitar")
    assert Step("a", "b").command is None
