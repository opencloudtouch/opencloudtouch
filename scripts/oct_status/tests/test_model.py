import dataclasses

import pytest

from oct_status.model import Edge, EdgeType, Graph, Phase, Resolution, Snapshot, Wait


def make_snapshot(number: int = 1) -> Snapshot:
    return Snapshot(
        number=number,
        is_pr=False,
        title="t",
        body="",
        state="open",
        merged=False,
        draft=False,
        author="a",
        author_permission=None,
        labels=frozenset(),
        base_ref="main",
        head_ref="",
        head_sha="",
        reviews=(),
        unresolved_threads=0,
        checks=(),
        closing_refs=(),
        sub_issues=(),
        blocked_by=(),
        pushes=(),
        stack_drift=None,
    )


def test_snapshot_is_frozen_and_graph_edges_of_filters():
    snap = make_snapshot(537)
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.title = "x"  # type: ignore[misc]
    edges = [
        Edge(EdgeType.IMPLEMENTED_BY, 537, 600, "native"),
        Edge(EdgeType.RELATED, 537, 601, "prose"),
        Edge(EdgeType.IMPLEMENTED_BY, 700, 701, "native"),
    ]
    graph = Graph(edges=edges, snapshots={537: snap}, derived={})
    assert graph.edges_of(537, EdgeType.IMPLEMENTED_BY) == [edges[0]]
    assert graph.edges_of(537) == edges[:2]


def test_enum_labels():
    assert Phase.IN_PROGRESS.label == "phase:in-progress"
    assert Wait.HARDWARE_TEST.label == "wait:hardware-test"
    assert Resolution.NOT_REPRODUCIBLE.label == "resolution:not-reproducible"
