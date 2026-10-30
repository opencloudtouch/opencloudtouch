"""Derivation of waits and phases (design section 6 is the oracle)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from oct_status.config import load_config
from oct_status.graph import inverse
from oct_status.model import Check, Edge, EdgeType, Graph, Kind, Phase, Push, Resolution, Review, Snapshot, Wait
from oct_status.rules import ANNOUNCEMENT_DERIVED, derive

from .conftest import make_snapshot

CFG = load_config(Path(__file__).parent.parent / "config.yml")
HEAD = "c3"
DOR_DONE = "## Definition of Ready\n- [x] Problem described\n- [x] Tests named\n"
GREEN = (Check("CI Summary", "completed", "success", "github-actions"),)


def pr(**overrides) -> Snapshot:
    """An open, ready, green PR by a non-maintainer with three commits by its author."""
    values = {
        "number": 10,
        "is_pr": True,
        "title": "feat: thing",
        "author": "alice",
        "author_permission": "write",
        "head_ref": "feat/thing",
        "base_ref": "main",
        "head_sha": HEAD,
        "checks": GREEN,
        "pushes": (Push("c1", "alice", ()), Push("c2", "alice", ()), Push(HEAD, "alice", ())),
    }
    values.update(overrides)
    return make_snapshot(**values)


def spec(**overrides) -> Snapshot:
    values = {"number": 5, "title": "Sleep timer", "labels": frozenset({"spec"}), "body": DOR_DONE}
    values.update(overrides)
    return make_snapshot(**values)


def plan(**overrides) -> Snapshot:
    values = {"number": 30, "title": "[Test] Sleep timer on hardware"}
    values.update(overrides)
    return make_snapshot(**values)


def edge(type_: EdgeType, source: int, target: int) -> Edge:
    return Edge(type_, source, target, "native")


def run(snap: Snapshot, *others: Snapshot, edges: tuple[Edge, ...] = (), kind: Kind | None = None):
    all_edges: list[Edge] = []
    for e in edges:
        all_edges += [e, inverse(e)]
    graph = Graph(all_edges, {s.number: s for s in (snap, *others)}, {})
    return derive(snap, graph, CFG, kind=kind) if kind else derive(snap, graph, CFG)


APPROVED_BY_BOB = (Review("bob", "APPROVED", HEAD),)


# --- wait:maintainer -------------------------------------------------------------------------


def test_wait_maintainer_for_maintainer_pr():
    maintainer = {"author": "scheilch", "author_permission": "admin"}
    assert Wait.MAINTAINER in run(pr(**maintainer)).waits
    on_head = (Review("oct-support", "APPROVED", HEAD),)
    assert Wait.MAINTAINER not in run(pr(**maintainer, reviews=on_head)).waits
    older = (Review("oct-support", "APPROVED", "c2"),)
    assert Wait.MAINTAINER in run(pr(**maintainer, reviews=older)).waits
    # A human approval is not the maintainer approval for a maintainer-authored PR.
    assert Wait.MAINTAINER in run(pr(**maintainer, reviews=APPROVED_BY_BOB)).waits
    # A draft never waits for the maintainer.
    assert Wait.MAINTAINER not in run(pr(**maintainer, draft=True)).waits


@pytest.mark.parametrize("bot", ["gitar-bot[bot]", "github-code-quality[bot]", "sonarqubecloud[bot]"])
@pytest.mark.parametrize("permission", ["admin", "write"])
def test_other_bots_never_approve(bot, permission):
    snap = pr(
        author_permission=permission,
        reviews=(Review(bot, "APPROVED", HEAD),),
        labels=frozenset({"gitar-approved"}),
    )
    assert Wait.MAINTAINER in run(snap).waits


def test_foreign_pr_needs_human_write_approval():
    assert Wait.MAINTAINER in run(pr()).waits
    assert Wait.MAINTAINER in run(pr(author_permission=None)).waits
    assert Wait.MAINTAINER not in run(pr(reviews=APPROVED_BY_BOB)).waits
    # oct-support is automation: its approval is the maintainer approval only for maintainer PRs.
    assert Wait.MAINTAINER in run(pr(reviews=(Review("oct-support", "APPROVED", HEAD),))).waits
    # The author never approves their own PR.
    assert Wait.MAINTAINER in run(pr(reviews=(Review("alice", "APPROVED", HEAD),))).waits
    # A later change request by the same reviewer withdraws the approval; a comment does not.
    withdrawn = (*APPROVED_BY_BOB, Review("bob", "CHANGES_REQUESTED", HEAD))
    assert Wait.MAINTAINER in run(pr(reviews=withdrawn)).waits
    commented = (*APPROVED_BY_BOB, Review("bob", "COMMENTED", HEAD))
    assert Wait.MAINTAINER not in run(pr(reviews=commented)).waits


@pytest.mark.parametrize(
    ("pusher", "approved"),
    [
        ("formatter-bot", True),
        ("gitar-bot[bot]", False),
        ("alice", False),
        ("dependabot[bot]", False),  # automation, but invalidates_approval defaults to true
        ("Formatter Bot", False),  # a git author name that is not an allowlisted login
        ("", False),
    ],
)
def test_formatter_bot_push_keeps_approval_gitar_push_invalidates(pusher, approved):
    pushes = (Push("c2", "alice", ()), Push(HEAD, "alice", ()), Push("c4", pusher, ()))
    reviews = (Review("bob", "APPROVED", HEAD),)
    snap = pr(head_sha="c4", pushes=pushes, reviews=reviews)
    assert (Wait.MAINTAINER not in run(snap).waits) is approved
    maintainer = pr(
        author_permission="maintain",
        head_sha="c4",
        pushes=pushes,
        reviews=(Review("oct-support", "APPROVED", HEAD),),
    )
    assert (Wait.MAINTAINER not in run(maintainer).waits) is approved


def test_approval_on_unknown_commit_does_not_count():
    # The approved commit is not among the known pushes (force push or beyond the 100-commit window).
    assert Wait.MAINTAINER in run(pr(reviews=(Review("bob", "APPROVED", "gone"),))).waits
    assert Wait.MAINTAINER in run(pr(reviews=(Review("bob", "APPROVED", ""),), head_sha="")).waits


# --- wait:findings and wait:ci ---------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"unresolved_threads": 2},
        {"reviews": (Review("gitar-bot[bot]", "CHANGES_REQUESTED", HEAD),)},
        {"reviews": (Review("gitar-bot[bot]", "APPROVED", "c1"), Review("gitar-bot[bot]", "CHANGES_REQUESTED", HEAD))},
        {"checks": (*GREEN, Check("SonarCloud Code Analysis", "completed", "failure", "sonarqubecloud"))},
        {"checks": (*GREEN, Check("Gitar", "completed", "failure", "gitar"))},
    ],
)
def test_findings(overrides):
    derived = run(pr(**overrides))
    assert Wait.FINDINGS in derived.waits
    assert Wait.CI not in derived.waits


@pytest.mark.parametrize(
    "overrides",
    [
        {"unresolved_threads": -1},  # unknown is not a finding
        {"reviews": (Review("gitar-bot[bot]", "CHANGES_REQUESTED", "c1"), Review("gitar-bot[bot]", "APPROVED", HEAD))},
        {"reviews": (Review("gitar-bot[bot]", "CHANGES_REQUESTED", "c1"), Review("gitar-bot[bot]", "DISMISSED", "c1"))},
        {"reviews": (Review("bob", "CHANGES_REQUESTED", HEAD),)},
    ],
)
def test_no_findings(overrides):
    assert Wait.FINDINGS not in run(pr(**overrides)).waits


def test_ci_ignores_skipped_and_absent_checks():
    checks = (
        *GREEN,
        Check("SonarCloud Code Analysis", "completed", "skipped", "sonarqubecloud"),
        Check("lint (not a gate)", "completed", "failure", "github-actions"),
    )
    assert run(pr(checks=checks)).waits & {Wait.CI, Wait.FINDINGS} == frozenset()
    assert Wait.CI not in run(pr(checks=())).waits


@pytest.mark.parametrize(
    "check",
    [
        Check("CI Summary", "in_progress", None, "github-actions"),
        Check("CI Summary", "queued", None, "github-actions"),
        Check("CI Summary", "completed", "failure", "github-actions"),
        Check("CI Summary", "completed", "timed_out", "github-actions"),
        Check("SonarCloud Code Analysis", "in_progress", None, "sonarqubecloud"),
    ],
)
def test_ci_pending_gate_sets_wait(check):
    derived = run(pr(checks=(check,)))
    assert Wait.CI in derived.waits
    assert Wait.FINDINGS not in derived.waits


# --- wait:prerequisite and wait:hardware-test ------------------------------------------------


def test_prerequisite():
    parent = pr(number=9, head_ref="feat/base", reviews=APPROVED_BY_BOB)
    child = pr(base_ref="feat/base", reviews=APPROVED_BY_BOB)
    stacked = (edge(EdgeType.STACKED_ON, 10, 9),)
    assert Wait.PREREQUISITE in run(child, parent, edges=stacked).waits
    merged_parent = pr(number=9, state="closed", merged=True)
    assert Wait.PREREQUISITE not in run(child, merged_parent, edges=stacked).waits

    depends = (edge(EdgeType.DEPENDS_ON, 10, 7),)
    assert Wait.PREREQUISITE in run(child, make_snapshot(number=7), edges=depends).waits
    assert Wait.PREREQUISITE not in run(child, make_snapshot(number=7, state="closed"), edges=depends).waits
    # A neighbour outside the fetched graph cannot be judged and does not block.
    assert Wait.PREREQUISITE not in run(child, edges=depends).waits


def test_prerequisite_implements_spec_not_ready():
    implements = (edge(EdgeType.IMPLEMENTS, 10, 5),)
    draft_spec = spec(labels=frozenset({"spec", "phase:draft"}))
    assert Wait.PREREQUISITE in run(pr(), draft_spec, edges=implements).waits
    ready_spec = spec(labels=frozenset({"spec", "phase:ready"}))
    assert Wait.PREREQUISITE not in run(pr(), ready_spec, edges=implements).waits
    in_review = spec(labels=frozenset({"spec", "phase:in-review"}))
    assert Wait.PREREQUISITE not in run(pr(), in_review, edges=implements).waits
    unticked = spec(labels=frozenset({"spec", "phase:ready"}), body="## Definition of Ready\n- [ ] Tests named\n")
    assert Wait.PREREQUISITE in run(pr(), unticked, edges=implements).waits
    # Bugs and feature requests have no `ready` phase: implementing them needs no prerequisite.
    bug = make_snapshot(number=5, labels=frozenset({"bug"}))
    assert Wait.PREREQUISITE not in run(pr(), bug, edges=implements).waits


def test_hardware_test_from_open_test_plan():
    verifies = (edge(EdgeType.VERIFIES, 30, 10),)
    derived = run(pr(), plan(), edges=verifies)
    assert Wait.HARDWARE_TEST in derived.waits
    merged = run(pr(state="closed", merged=True), plan(), edges=verifies)
    assert merged.phase == Phase.MERGED
    assert merged.waits == frozenset({Wait.HARDWARE_TEST})  # merging does not clear it


def test_test_plan_closed_clears_target_hardware_wait():
    verifies = (edge(EdgeType.VERIFIES, 30, 10),)
    declared = pr(labels=frozenset({"wait:hardware-test"}))
    assert Wait.HARDWARE_TEST not in run(declared, plan(state="closed"), edges=verifies).waits
    # Without any test plan, the declared wait stays until `/oct verified` removes the label.
    assert Wait.HARDWARE_TEST in run(declared).waits
    # The same for a spec verified directly.
    on_spec = (edge(EdgeType.VERIFIES, 30, 5),)
    open_spec = spec(labels=frozenset({"spec", "phase:ready", "wait:hardware-test"}))
    assert Wait.HARDWARE_TEST in run(open_spec, plan(), edges=on_spec).waits
    assert Wait.HARDWARE_TEST not in run(open_spec, plan(state="closed"), edges=on_spec).waits


# --- phases ----------------------------------------------------------------------------------


def test_phase_for_pr_and_spec():
    assert run(pr(draft=True)).phase == Phase.DRAFT
    assert run(pr()).phase == Phase.IN_REVIEW
    assert run(pr(state="closed", merged=True)).phase == Phase.MERGED
    closed = run(pr(state="closed", labels=frozenset({"resolution:abandoned"})))
    assert (closed.phase, closed.resolution, closed.waits) == (Phase.CLOSED, Resolution.ABANDONED, frozenset())

    implements = (edge(EdgeType.IMPLEMENTS, 10, 5),)
    ready = spec(labels=frozenset({"spec", "phase:ready"}))
    assert run(ready, pr(), edges=implements).phase == Phase.IN_REVIEW
    assert run(ready, pr(draft=True), edges=implements).phase == Phase.IN_PROGRESS

    merged_pr = pr(state="closed", merged=True)
    on_spec = (*implements, edge(EdgeType.VERIFIES, 30, 5))
    verification = run(ready, merged_pr, plan(), edges=on_spec)
    assert verification.phase == Phase.VERIFICATION
    assert Wait.HARDWARE_TEST in verification.waits
    # A test plan naming the PR also holds the spec in verification.
    via_pr = (*implements, edge(EdgeType.VERIFIES, 30, 10))
    assert run(ready, merged_pr, plan(), edges=via_pr).phase == Phase.VERIFICATION

    done = run(replace(ready, state="closed"), merged_pr, edges=implements)
    assert (done.phase, done.waits, done.resolution) == (Phase.DONE, frozenset(), None)
    # Closed but still waiting for hardware: verification, not done.
    hw = spec(state="closed", labels=frozenset({"spec", "wait:hardware-test"}))
    assert run(hw, merged_pr, edges=implements).phase == Phase.VERIFICATION
    # Open, every known part merged, nothing waits: more parts may follow, so not done yet.
    assert run(ready, merged_pr, edges=implements).phase == Phase.IN_PROGRESS
    dropped = run(spec(state="closed", labels=frozenset({"spec", "resolution:wontfix"})))
    assert (dropped.phase, dropped.resolution) == (Phase.CLOSED, Resolution.WONTFIX)


def test_closed_pr_part_is_ignored_and_wip_label_means_in_progress():
    implements = (edge(EdgeType.IMPLEMENTS, 10, 5),)
    ready = spec(labels=frozenset({"spec", "phase:ready"}))
    assert run(ready, pr(state="closed"), edges=implements).phase == Phase.READY
    bug = make_snapshot(number=5, labels=frozenset({"bug", "wip"}))
    assert run(bug).phase == Phase.IN_PROGRESS


def test_tracking_phase_from_children():
    tracking = make_snapshot(number=40, title="[Tracking] Sleep timer", sub_issues=(5, 6))
    tracks = (edge(EdgeType.TRACKS, 40, 5), edge(EdgeType.TRACKS, 40, 6))
    closed5, open6 = make_snapshot(number=5, state="closed"), make_snapshot(number=6)
    assert run(tracking, closed5, open6, edges=tracks).phase == Phase.IN_PROGRESS
    closed6 = make_snapshot(number=6, state="closed")
    assert run(tracking, closed5, closed6, edges=tracks).phase == Phase.DONE
    # A child outside the fetched graph counts as open.
    assert run(tracking, closed5, edges=tracks).phase == Phase.IN_PROGRESS
    assert run(tracking).phase == Phase.NEW


def test_test_plan_phases():
    assert run(plan()).phase == Phase.NEW
    assert run(plan(labels=frozenset({"phase:in-progress"}))).phase == Phase.IN_PROGRESS
    assert run(plan(state="closed")).phase == Phase.DONE


def test_feature_request_mirrors_spec_and_closes_with_it():
    request = make_snapshot(number=3, title="Please add a sleep timer", labels=frozenset({"enhancement"}))
    specified = (edge(EdgeType.SPECIFIED_BY, 3, 5),)
    reviewing = spec(labels=frozenset({"spec", "phase:spec-review"}))
    mirrored = run(request, reviewing, edges=specified)
    assert (mirrored.phase, mirrored.resolution) == (Phase.SPEC_REVIEW, None)

    done_spec = spec(state="closed")
    assert run(request, done_spec, edges=specified).phase == Phase.DONE

    dropped_spec = spec(state="closed", labels=frozenset({"spec", "resolution:wontfix"}))
    dropped = run(request, dropped_spec, edges=specified)
    assert (dropped.phase, dropped.resolution) == (Phase.CLOSED, Resolution.SUPERSEDED)
    # An already derived spec in the graph is used as is.
    graph = Graph([*specified, inverse(specified[0])], {3: request, 5: reviewing}, {})
    graph.derived[5] = derive(spec(labels=frozenset({"spec", "phase:spec-rework"})), graph, CFG)
    assert derive(request, graph, CFG).phase == Phase.SPEC_REWORK


def test_feature_request_mirrors_only_specs():
    # A `specified-by` edge to another request (malformed data) is ignored and cannot recurse.
    first = make_snapshot(number=3, labels=frozenset({"enhancement", "phase:triaged"}))
    second = make_snapshot(number=4, labels=frozenset({"enhancement"}))
    loop = (edge(EdgeType.SPECIFIED_BY, 3, 4), edge(EdgeType.SPECIFIED_BY, 4, 3))
    assert run(first, second, edges=loop).phase == Phase.TRIAGED


def test_unlabeled_issue_is_a_new_feature_request():
    assert run(make_snapshot(number=3)).phase == Phase.NEW


def test_discussion_phases():
    d = make_snapshot(number=50, title="Idea")
    assert run(d, kind=Kind.DISCUSSION).phase == Phase.OPEN
    needs = make_snapshot(number=50, labels=frozenset({"phase:needs-spec"}))
    assert run(needs, kind=Kind.DISCUSSION).phase == Phase.NEEDS_SPEC
    specified = (edge(EdgeType.SPECIFIED_BY, 50, 5),)
    assert run(needs, spec(), edges=specified, kind=Kind.DISCUSSION).phase == Phase.SPECIFIED
    answered = make_snapshot(number=50, labels=frozenset({"phase:answered"}))
    assert run(answered, kind=Kind.DISCUSSION).phase == Phase.ANSWERED
    assert run(make_snapshot(number=50, state="closed"), kind=Kind.DISCUSSION).phase == Phase.CLOSED


def test_announcement_gets_neutral_derived():
    release = make_snapshot(number=60, author="github-actions[bot]", labels=frozenset({"phase:new", "wait:ci"}))
    assert run(release) == ANNOUNCEMENT_DERIVED
    assert ANNOUNCEMENT_DERIVED.waits == frozenset()
    assert ANNOUNCEMENT_DERIVED.resolution is None


def test_declared_waits_kept_while_open_and_fact_labels_ignored():
    labels = frozenset({"spec", "wait:spec-fix", "wait:designer", "wait:ci", "wait:maintainer"})
    assert run(spec(labels=labels)).waits == frozenset({Wait.SPEC_FIX, Wait.DESIGNER})
    assert run(spec(labels=labels, state="closed")).waits == frozenset()


def test_mergeable_means_no_wait():
    checks = (
        *GREEN,
        Check("SonarCloud Code Analysis", "completed", "success", "sonarqubecloud"),
        Check("Gitar", "completed", "neutral", "gitar"),
    )
    reviews = (Review("gitar-bot[bot]", "APPROVED", HEAD), *APPROVED_BY_BOB)
    implements = (edge(EdgeType.IMPLEMENTS, 10, 5),)
    ready_spec = spec(labels=frozenset({"spec", "phase:ready"}))
    derived = run(pr(checks=checks, reviews=reviews), ready_spec, edges=implements)
    assert derived.phase == Phase.IN_REVIEW
    assert derived.waits == frozenset()
    assert derived.resolution is None
