"""Tests for the violation detectors V01-V08 and the escalation ladder."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from oct_status.config import load_config
from oct_status.graph import inverse
from oct_status.guide import format_notice, render_guide
from oct_status.model import Derived, Edge, EdgeType, Graph, Phase, Snapshot, Wait
from oct_status.render import render_block
from oct_status.rules import derive
from oct_status.violations import (
    RULES,
    EventFacts,
    Violation,
    classify_actor,
    detect,
    escalate,
)

from .conftest import make_snapshot
from .test_rules import pr, spec

CFG = load_config(Path(__file__).parent.parent / "config.yml")
HUMAN = "human"
IMPLEMENTS = (Edge(EdgeType.IMPLEMENTS, 10, 5, "native"),)


def graph_of(*snaps: Snapshot, edges: tuple[Edge, ...] = ()) -> Graph:
    all_edges: list[Edge] = []
    for e in edges:
        all_edges += [e, inverse(e)]
    graph = Graph(all_edges, {s.number: s for s in snaps}, {})
    for s in snaps:
        if (d := derive(s, graph, CFG)) is not None:
            graph.derived[s.number] = d
    return graph


def rules_of(snap: Snapshot, *others: Snapshot, edges=(), actor_class=HUMAN, event=None) -> list[str]:
    graph = graph_of(snap, *others, edges=edges)
    derived = graph.derived.get(snap.number) or Derived(Phase.NEW, frozenset(), None)
    return [v.rule for v in detect(snap, derived, graph, CFG, actor_class, event)]


# --- V01 -----------------------------------------------------------------------------------------


def test_v01_pr_without_spec_edge():
    assert rules_of(pr()) == ["V01"]
    assert "V01" not in rules_of(pr(), spec(), edges=IMPLEMENTS)


def test_v01_waived_by_no_spec_and_dependency_pr_and_closed_pr():
    assert rules_of(pr(no_spec_reason="typo")) == []
    assert rules_of(pr(author="dependabot[bot]")) == []
    assert rules_of(pr(state="closed")) == []
    assert rules_of(pr(merged=True, state="closed")) == []
    assert rules_of(make_snapshot(number=10)) == []  # an issue is not a pull request
    # A docs-type PR needs no spec edge (design section 4.1) ...
    assert rules_of(pr(title="docs: readme")) == []


def test_v01_user_is_the_author():
    graph = graph_of(pr())
    (v,) = detect(pr(), graph.derived[10], graph, CFG, HUMAN)
    assert (v.rule, v.artifact, v.user) == ("V01", 10, "alice")


def test_automation_and_first_time_fork_authors_exempt():
    assert rules_of(pr(author="gitar-bot[bot]")) == []
    assert rules_of(pr(author="formatter-bot")) == []
    assert rules_of(pr(), actor_class="first-timer") == []
    fork = pr(head_is_fork=True, author_association="FIRST_TIME_CONTRIBUTOR")
    assert classify_actor(fork, CFG) == "first-timer"
    assert classify_actor(replace(fork, author_association="FIRST_TIMER"), CFG) == "first-timer"
    assert classify_actor(replace(fork, author_association="CONTRIBUTOR"), CFG) == HUMAN
    assert classify_actor(replace(fork, head_is_fork=False), CFG) == HUMAN  # not a fork
    assert classify_actor(pr(author="gitar-bot[bot]"), CFG) == "automation"
    assert classify_actor(pr(author="alice", author_permission="admin", author_association="OWNER"), CFG) == HUMAN


def test_event_rules_skip_automation_and_bot_actors():
    label = EventFacts("labeled", "gitar-bot[bot]", "phase:done")
    assert rules_of(make_snapshot(), event=label) == []
    label = EventFacts("labeled", "oct-support", "phase:done")
    assert rules_of(make_snapshot(), event=label) == []
    label = EventFacts("labeled", "github-actions[bot]", "phase:done")
    assert rules_of(make_snapshot(), event=label) == []
    assert rules_of(make_snapshot(), event=EventFacts("labeled", "", "phase:done")) == []  # unattributable


# --- V02 -----------------------------------------------------------------------------------------


def test_v02_fact_label_set_or_removed_by_hand():
    issue = make_snapshot()
    for action in ("labeled", "unlabeled"):
        assert rules_of(issue, event=EventFacts(action, "bob", "phase:done")) == ["V02"]
    assert rules_of(issue, event=EventFacts("labeled", "bob", "wait:ci")) == ["V02"]
    # Declarations and foreign labels may be set by label.
    for label in ("phase:triaged", "phase:ready", "wait:reporter", "resolution:wontfix", "bug", "wip"):
        assert rules_of(issue, event=EventFacts("labeled", "bob", label)) == []
    assert rules_of(issue, event=EventFacts("edited", "bob", "phase:done")) == []


def test_v02_user_is_the_event_actor():
    snap = make_snapshot()
    graph = graph_of(snap)
    (v,) = detect(snap, graph.derived[1], graph, CFG, HUMAN, EventFacts("labeled", "bob", "phase:done"))
    assert (v.rule, v.user) == ("V02", "bob")
    assert "phase:done" in v.hint


def test_v02_exempt_author_actor_stays_exempt():
    snap = pr(author="alice")
    assert (
        rules_of(
            snap, spec(), edges=IMPLEMENTS, actor_class="first-timer", event=EventFacts("labeled", "alice", "wait:ci")
        )
        == []
    )
    assert rules_of(
        snap, spec(), edges=IMPLEMENTS, actor_class="first-timer", event=EventFacts("labeled", "bob", "wait:ci")
    ) == ["V02"]


# --- V03 and V05 ---------------------------------------------------------------------------------


def _with_block(body: str) -> tuple[Snapshot, str]:
    snap = pr(body=body)
    graph = graph_of(snap)
    block = render_block(snap, graph.derived[10], graph, CFG)
    assert block
    return replace(snap, body=f"{block}\n{body}"), block


def test_v03_block_removed_or_edited_by_hand():
    snap, block = _with_block("Part of #5")
    before = snap.body
    edited = EventFacts("edited", "bob", body_before=before)
    assert "V03" not in rules_of(snap, spec(), edges=IMPLEMENTS, event=edited)  # block unchanged
    removed = replace(snap, body="Part of #5")
    assert "V03" in rules_of(removed, spec(), edges=IMPLEMENTS, event=edited)
    tampered = replace(snap, body=before.replace("Ball with", "Ball w1th", 1))
    assert "V03" in rules_of(tampered, spec(), edges=IMPLEMENTS, event=edited)
    assert "V03" not in rules_of(
        removed, spec(), edges=IMPLEMENTS, event=EventFacts("edited", "bob", body_before="Part of #5")
    )
    assert "V03" not in rules_of(
        removed, spec(), edges=IMPLEMENTS, event=EventFacts("edited", "oct-support", body_before=before)
    )
    assert "V03" not in rules_of(removed, spec(), edges=IMPLEMENTS, event=EventFacts("edited", "bob"))
    # An intact block is fine whatever the body looked like before (the state may simply have changed).
    other_before = EventFacts("edited", "bob", body_before=before.replace("Ball with", "Ball w1th", 1))
    assert "V03" not in rules_of(snap, spec(), edges=IMPLEMENTS, event=other_before)


TEMPLATE = "## Summary\n\ntext\n\n## Definition of Done\n- [ ] Tests added\n- [x] Deviations from the spec (and why): <!-- none -->\n"


def test_v05_template_section_or_item_deleted():
    snap = pr(body=TEMPLATE)
    kw = {"edges": IMPLEMENTS}

    def v05(body: str) -> bool:
        event = EventFacts("edited", "bob", body_before=TEMPLATE)
        return "V05" in rules_of(replace(snap, body=body), spec(), event=event, **kw)

    assert not v05(TEMPLATE)
    assert not v05(TEMPLATE.replace("text", "more text"))  # content may change
    assert not v05(TEMPLATE.replace("- [ ] Tests added", "- [x] Tests added"))  # ticking is fine
    assert not v05(TEMPLATE.replace("(and why): <!-- none -->", "(and why): none"))  # filling an item in is fine
    assert v05(TEMPLATE.replace("## Definition of Done\n- [ ] Tests added\n", "- [ ] Tests added\n"))
    assert v05(TEMPLATE.replace("- [ ] Tests added\n", ""))
    assert v05(TEMPLATE.replace("- [x] Deviations from the spec (and why): <!-- none -->\n", ""))
    # A plain issue has no template to protect.
    plain = make_snapshot(body="")
    assert "V05" not in rules_of(plain, event=EventFacts("edited", "bob", body_before=TEMPLATE))


def test_v05_is_not_triggered_by_a_replaced_status_block():
    snap, _ = _with_block(TEMPLATE)
    old = snap.body.replace("Ball with", "Ball w1th")
    assert "V05" not in rules_of(snap, spec(), edges=IMPLEMENTS, event=EventFacts("edited", "bob", body_before=old))


# --- V04 and V06 ---------------------------------------------------------------------------------


def test_v04_ready_pr_with_open_prerequisite():
    dep = (Edge(EdgeType.DEPENDS_ON, 10, 7, "native"),)
    base = (*IMPLEMENTS, *dep)
    open_dep = make_snapshot(number=7, is_pr=True, head_ref="feat/parent")
    assert "V04" in rules_of(pr(), spec(), open_dep, edges=base)
    assert "V04" not in rules_of(pr(draft=True), spec(), open_dep, edges=base)  # a draft may wait
    merged = replace(open_dep, merged=True, state="closed")
    assert "V04" not in rules_of(pr(), spec(), merged, edges=base)
    assert "V04" not in rules_of(pr(base_ref="feat/parent"), spec(), open_dep, edges=base)  # stacked on it
    assert "V04" in rules_of(pr(base_ref="other"), spec(), open_dep, edges=base)
    assert "V04" not in rules_of(pr(), spec(), edges=base)  # prerequisite outside the graph
    open_issue = make_snapshot(number=7)
    assert "V04" in rules_of(pr(), spec(), open_issue, edges=base)


def test_v06_pr_for_a_spec_that_is_not_ready():
    draft = spec(labels=frozenset({"spec"}), body="## Definition of Ready\n- [ ] Tests named\n")
    assert "V06" in rules_of(pr(), draft, edges=IMPLEMENTS)
    ready = spec(labels=frozenset({"spec", "phase:ready"}))
    assert "V06" not in rules_of(pr(), ready, edges=IMPLEMENTS)
    # A bug has no ready phase.
    assert "V06" not in rules_of(pr(), make_snapshot(number=5, labels=frozenset({"bug"})), edges=IMPLEMENTS)
    # A hand-set fact label on a draft spec does not make it ready (V02 guard).
    forged = spec(labels=frozenset({"spec", "phase:in-review"}), body="## Definition of Ready\n- [ ] x\n")
    assert "V06" in rules_of(pr(), forged, edges=IMPLEMENTS)
    assert "V06" not in rules_of(pr(state="closed"), draft, edges=IMPLEMENTS)


# --- V07 and V08 ---------------------------------------------------------------------------------


def test_v07_invalid_declaration():
    issue = make_snapshot()
    event = EventFacts("created", "alice", rejected="/oct ready was rejected: The Definition of Ready is incomplete")
    assert rules_of(issue, event=event) == ["V07"]
    assert rules_of(issue, event=EventFacts("created", "alice")) == []
    snap = make_snapshot()
    graph = graph_of(snap)
    (v,) = detect(snap, graph.derived[1], graph, CFG, HUMAN, event)
    assert v.user == "alice" and "incomplete" in v.hint


def test_v08_closing_a_verification_artifact_without_verified():
    hw = spec(state="closed", labels=frozenset({"spec", "wait:hardware-test"}))
    graph = graph_of(hw)
    assert graph.derived[5].phase == Phase.VERIFICATION and Wait.HARDWARE_TEST in graph.derived[5].waits
    closed = EventFacts("closed", "bob", state_reason="completed", closed_by_change=False)
    assert rules_of(hw, event=closed) == ["V08"]
    verified = spec(state="closed", labels=frozenset({"spec"}))  # /oct verified removed the wait
    assert rules_of(verified, event=closed) == []
    assert rules_of(hw, event=EventFacts("edited", "bob")) == []
    assert rules_of(hw, event=replace(closed, actor="oct-support")) == []
    dropped = spec(state="closed", labels=frozenset({"spec", "wait:hardware-test", "resolution:wontfix"}))
    assert rules_of(dropped, event=closed) == []  # closed without a fix is not a verification


def test_v08_not_charged_for_merge_closes_not_planned_or_unknown_closer():
    hw = spec(state="closed", labels=frozenset({"spec", "wait:hardware-test"}))
    base = EventFacts("closed", "bob", state_reason="completed", closed_by_change=False)
    assert rules_of(hw, event=replace(base, closed_by_change=True)) == []  # closed by a merged PR
    assert rules_of(hw, event=replace(base, closed_by_change=None)) == []  # unknown: fail closed
    assert rules_of(hw, event=replace(base, state_reason="not_planned")) == []
    assert rules_of(hw, event=replace(base, state_reason=None)) == []


# --- ladder --------------------------------------------------------------------------------------


V = Violation("V01", 10, "alice", "This pull request has no reference.")


def test_ladder_messages():
    one = format_notice(escalate(V, 1), True)
    assert "docs/WORKFLOW.md#v01-" in one and "V01" in one and "Next steps" in one
    assert "/oct override" not in one and "fails" not in one
    two = format_notice(escalate(V, 2), True)
    assert "/oct override" in two and "fails" not in two
    for level in (3, 4):
        three = format_notice(escalate(V, level), True)
        assert "/oct override" in three and "oct-status fails" in three
        assert escalate(V, level).blocks(True) is True and escalate(V, level).revert(True) is False
        assert escalate(V, level).revert(False) is True and escalate(V, level).blocks(False) is False
        assert "reverted" in format_notice(escalate(V, level), False)
    assert not escalate(V, 2).blocks(True) and not escalate(V, 2).revert(False)
    assert escalate(V, 0).level == 1  # inactive strikes and an unreadable ledger never escalate


def test_overridden_notice_is_resolved():
    text = format_notice(escalate(V, 3, overridden=True), True)
    assert text.startswith("[resolved] ") and "overridden" in text and "fails" not in text


def test_every_rule_has_anchor_and_next_steps():
    assert sorted(RULES) == [f"V0{i}" for i in range(1, 9)]
    anchors = {r.anchor for r in RULES.values()}
    assert len(anchors) == 8 and all(a.startswith(f"v0{i + 1}-") for i, a in enumerate(a for a in sorted(anchors)))
    for rule in RULES:
        text = format_notice(escalate(Violation(rule, 1, "u", "hint."), 1), True)
        assert RULES[rule].anchor in text and RULES[rule].steps[0].rstrip(".") in text


def test_notice_text_cannot_inject_markup():
    evil = Violation("V02", 1, "bob", "The label `x` <!-- /oct-status --> gitar-bot")
    guide = render_guide(
        make_snapshot(), Derived(Phase.NEW, frozenset(), None), [], [format_notice(escalate(evil, 1), False)], []
    )
    assert "<!-- /oct-status -->" not in guide
