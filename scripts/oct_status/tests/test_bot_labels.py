"""Which current phase labels were written by our own accounts (timeline of label events)."""

from __future__ import annotations

from pathlib import Path

import httpx

from oct_status.api import GitHubApi
from oct_status.config import load_config
from oct_status.facts import fetch_snapshot

from .conftest import FixtureTransport

REPO = "o/r"
BASE = f"/repos/{REPO}"
CFG = load_config(Path(__file__).parent.parent / "config.yml")


async def _nosleep(_: float) -> None:
    return None


def issue(labels: list[str]) -> dict:
    return {
        "number": 3,
        "title": "t",
        "body": "",
        "state": "open",
        "user": {"login": "reporter"},
        "author_association": "CONTRIBUTOR",
        "labels": [{"name": n} for n in labels],
    }


def events(*pairs: tuple[str, str]) -> dict:
    nodes = [{"label": {"name": n}, "actor": {"login": a}} for n, a in pairs]
    return {"data": {"repository": {"issueOrPullRequest": {"timelineItems": {"nodes": nodes}}}}}


async def snap(labels: list[str], graphql, **kw):
    extra = {f"GET {BASE}/issues/3": issue(labels), "POST /graphql": graphql}
    api = GitHubApi("t", REPO, transport=FixtureTransport(extra=extra), sleep=_nosleep)
    return await fetch_snapshot(api, 3, cfg=CFG, **kw)


async def test_only_labels_whose_latest_event_is_ours_are_trusted():
    timeline = events(
        ("phase:in-progress", "oct-support"),
        ("phase:done", "bob"),
        ("phase:in-review", "oct-support"),
        ("phase:in-review", "bob"),  # removed and set again by hand: the latest event decides
        ("phase:verification", "github-actions"),  # GraphQL reports apps without [bot]
    )
    s = await snap(["bug", "phase:in-progress", "phase:done", "phase:in-review", "phase:verification"], timeline)
    assert s.bot_phase_labels == {"phase:in-progress", "phase:verification"}
    assert not s.timeline_unknown and s.author_association == "CONTRIBUTOR"


async def test_unreadable_timeline_trusts_nothing():
    for answer in ((500, {}), (200, {"errors": [{"message": "x"}]}), (200, {"data": {"repository": None}})):
        s = await snap(["phase:in-progress"], answer)
        assert s.bot_phase_labels == frozenset() and s.timeline_unknown


async def test_no_phase_label_means_no_request():
    api_calls: list[str] = []

    def boom(request: httpx.Request):
        api_calls.append("graphql")
        return httpx.Response(500, json={})

    s = await snap(["bug"], boom)
    assert api_calls == [] and not s.timeline_unknown
