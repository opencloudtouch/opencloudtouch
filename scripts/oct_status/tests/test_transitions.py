"""Declarations: Definition of Ready checklist, legal transitions and validation of declared phases."""

from __future__ import annotations

from pathlib import Path

import pytest

from oct_status.config import load_config
from oct_status.model import Graph, Kind, Phase
from oct_status.rules import derive, dor_status, legal_transitions

from .conftest import make_snapshot

CFG = load_config(Path(__file__).parent.parent / "config.yml")

TICKED = """Intro

## Definition of Ready

- [x] Problem described
- [X] Acceptance criteria are testable
* [x] Prerequisites merged

## Definition of Done
- [ ] Tests green
"""
UNTICKED = TICKED.replace("- [X] Acceptance criteria are testable", "- [ ] Acceptance criteria are testable")


def derive_alone(**overrides):
    snap = make_snapshot(**overrides)
    return derive(snap, Graph([], {snap.number: snap}, {}), CFG)


def test_dor_status():
    assert dor_status(TICKED) == (True, [])
    assert dor_status(UNTICKED) == (False, ["Acceptance criteria are testable"])
    na = UNTICKED.replace("are testable", "are testable (n/a: no UI)")
    assert dor_status(na) == (True, [])
    assert dor_status("## Summary\n- [x] done\n") == (False, ["Definition of Ready section missing"])
    assert dor_status("") == (False, ["Definition of Ready section missing"])


def test_dor_status_form_heading_and_section_end():
    # Issue forms render fields as level-3 headings; the section ends at the next heading of that level.
    form = "### Definition of Ready\n\n- [x] Problem described\n#### Notes\n- [ ] sub item\n### Other\n- [ ] x\n"
    assert dor_status(form) == (False, ["sub item"])
    assert dor_status("## Definition of Ready\n\nnothing to tick\n") == (
        False,
        ["Definition of Ready section has no checklist items"],
    )


@pytest.mark.parametrize(
    ("kind", "phase", "commands"),
    [
        (Kind.SPEC, Phase.DRAFT, ["review"]),
        (Kind.SPEC, Phase.SPEC_REVIEW, ["rework", "ready"]),
        (Kind.SPEC, Phase.SPEC_REWORK, ["review", "ready"]),
        (Kind.SPEC, Phase.READY, []),
        (Kind.SPEC, Phase.IN_REVIEW, []),
        (Kind.BUG, Phase.NEW, ["triage"]),
        (Kind.BUG, Phase.TRIAGED, ["confirm"]),
        (Kind.FEATURE_REQUEST, Phase.NEW, ["triage"]),
        (Kind.FEATURE_REQUEST, Phase.TRIAGED, []),
        (Kind.PULL_REQUEST, Phase.IN_REVIEW, []),
        (Kind.ANNOUNCEMENT, Phase.OPEN, []),
    ],
)
def test_legal_transitions(kind, phase, commands):
    assert legal_transitions(kind, phase) == commands


def test_declared_phase_is_kept_and_illegal_one_rejected():
    rejected = derive_alone(labels=frozenset({"spec", "phase:ready"}), body=UNTICKED)
    assert rejected.phase == Phase.DRAFT
    assert "ready" not in legal_transitions(Kind.SPEC, rejected.phase)
    assert derive_alone(labels=frozenset({"spec", "phase:ready"}), body=TICKED).phase == Phase.READY
    assert derive_alone(labels=frozenset({"spec", "phase:spec-review"}), body=UNTICKED).phase == Phase.DRAFT
    assert derive_alone(labels=frozenset({"spec", "phase:spec-review"}), body=TICKED).phase == Phase.SPEC_REVIEW
    # Rework needs no complete checklist.
    assert derive_alone(labels=frozenset({"spec", "phase:spec-rework"}), body=UNTICKED).phase == Phase.SPEC_REWORK
    # Two phase labels: the furthest legal one wins.
    both = frozenset({"spec", "phase:spec-review", "phase:ready"})
    assert derive_alone(labels=both, body=TICKED).phase == Phase.READY


@pytest.mark.parametrize(
    ("labels", "phase"),
    [
        ({"bug", "phase:triaged"}, Phase.TRIAGED),
        ({"bug", "phase:confirmed"}, Phase.CONFIRMED),
        ({"enhancement", "phase:triaged"}, Phase.TRIAGED),
        ({"enhancement", "phase:confirmed"}, Phase.NEW),  # feature requests have no `confirmed`
        ({"bug", "phase:spec-review"}, Phase.NEW),  # foreign phase for the kind
        ({"bug", "phase:in-review"}, Phase.TRIAGED),  # a fact phase the bot wrote implies at least triaged
        ({"spec", "phase:in-progress"}, Phase.READY),  # ... and for a spec with a complete checklist `ready`
        ({"bug", "phase:bogus"}, Phase.NEW),
        ({"spec", "phase:triaged"}, Phase.DRAFT),
    ],
)
def test_declared_phase_validation_per_kind(labels, phase):
    # The bot wrote every label here; a hand-set fact label is covered in test_rules.
    snap = make_snapshot(labels=frozenset(labels), body=TICKED, bot_phase_labels=frozenset(labels))
    assert derive(snap, Graph([], {snap.number: snap}, {}), CFG).phase == phase
