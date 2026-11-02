"""Tests for the Ideenschmiede helpers (pure functions, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ideas import (
    STICKY_MARKER,
    Idea,
    discussion_body,
    idea_id_from_body,
    load_ideas,
    parse_idea,
    render_sticky,
    status_from_labels,
)

IDEA_TEXT = """---
id: 007
title: Example idea
summary: One line.
---
## Problem

Text.
"""


def test_parse_idea_reads_front_matter_and_body():
    idea = parse_idea(IDEA_TEXT)
    assert idea == Idea(id="007", title="Example idea", summary="One line.", body="## Problem\n\nText.\n")


def test_parse_idea_requires_id_and_title():
    with pytest.raises(ValueError):
        parse_idea("---\ntitle: x\n---\nbody")
    with pytest.raises(ValueError):
        parse_idea("no front matter")


def test_load_ideas_sorted_and_real_files_valid():
    ideas = load_ideas(Path(__file__).parents[3] / "docs" / "ideenschmiede" / "ideas")
    assert len(ideas) >= 6
    assert [i.id for i in ideas] == sorted(i.id for i in ideas)
    assert len({i.id for i in ideas}) == len(ideas)


def test_discussion_body_contains_marker_roundtrip():
    idea = parse_idea(IDEA_TEXT)
    body = discussion_body(idea, repo="o/r")
    assert idea_id_from_body(body) == "007"
    assert "Example idea" not in body.split("\n")[0]  # title is the discussion title, not repeated
    assert "👍" in body


def test_idea_id_from_body_none_for_foreign_discussion():
    assert idea_id_from_body("hello") is None
    assert idea_id_from_body(None) is None


@pytest.mark.parametrize(
    "labels,expected",
    [
        ([], "open"),
        (["idea:accepted"], "accepted"),
        (["bug", "idea:declined"], "declined"),
        (["idea:specced", "idea:accepted"], "specced"),  # furthest progress wins
        (["idea:declined", "idea:accepted"], "declined"),  # an explicit decline wins over accepted
    ],
)
def test_status_from_labels(labels, expected):
    assert status_from_labels(labels) == expected


def _row(number, title, up=0, down=0, comments=0, labels=()):
    return {
        "number": number,
        "title": title,
        "url": f"https://x/{number}",
        "upvotes": up,
        "downvotes": down,
        "comments": comments,
        "labels": list(labels),
        "author": "a",
    }


def test_render_sticky_sorts_open_by_votes_and_groups_decided():
    rows = [
        _row(1, "Low", up=1),
        _row(2, "High", up=5, down=1, comments=3),
        _row(3, "Done", up=9, labels=["idea:declined"]),
    ]
    out = render_sticky(rows, repo="o/r", generated="2026-11-02")
    assert out.startswith(STICKY_MARKER)
    assert out.index("High") < out.index("Low")
    open_part, decided_part = out.split("### Decided")
    assert "Done" not in open_part and "Done" in decided_part
    assert "| 5 | 1 |" in out  # votes column


def test_render_sticky_escapes_pipes_in_titles():
    out = render_sticky([_row(1, "a | b")], repo="o/r", generated="d")
    assert "a \\| b" in out


def test_render_sticky_empty():
    out = render_sticky([], repo="o/r", generated="d")
    assert "No ideas yet" in out


def test_missing_ideas_only_returns_unseeded():
    from main import missing_ideas

    ideas = [Idea("001", "a", "", ""), Idea("002", "b", "", "")]
    seeded = [{"body": "<!-- oct-idea:001 -->\ntext"}, {"body": "user written discussion"}]
    assert [i.id for i in missing_ideas(ideas, seeded)] == ["002"]


def test_strip_stamp_ignores_only_timestamp_line():
    from main import _strip_stamp

    assert _strip_stamp("a\n_Last updated 1_\nb") == "a\nb"
