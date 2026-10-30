from __future__ import annotations

import httpx

from oct_status.api import GitHubApi
from oct_status.facts import fetch_snapshot

from .conftest import FixtureTransport

REPO = "opencloudtouch/opencloudtouch"
BASE = f"/repos/{REPO}"


def _api(transport: httpx.AsyncBaseTransport) -> GitHubApi:
    return GitHubApi("t", REPO, transport=transport)


async def test_fetch_snapshot_pr():
    snap = await fetch_snapshot(_api(FixtureTransport([574])), 574, use_graphql=False)
    assert snap.is_pr
    assert snap.draft is True
    assert snap.base_ref == "feat/sleep-timer-backend"
    assert snap.head_ref == "feat/sleep-timer-frontend"
    assert 537 in snap.closing_refs
    assert snap.author == "scheilch"
    assert snap.head_is_fork is False
    assert snap.checks and snap.head_sha


async def test_fetch_snapshot_issue():
    snap = await fetch_snapshot(_api(FixtureTransport([537])), 537, use_graphql=False)
    assert not snap.is_pr
    assert snap.labels == frozenset({"enhancement", "spec"})
    assert snap.checks == () and snap.reviews == ()


async def test_fork_detected():
    transport = FixtureTransport([574])
    body = transport.routes[f"GET {BASE}/pulls/574"]
    body["head"]["repo"]["full_name"] = "someone/opencloudtouch"
    snap = await fetch_snapshot(_api(transport), 574, use_graphql=False)
    assert snap.head_is_fork is True


async def test_author_permission_fetched():
    perm = f"GET {BASE}/collaborators/scheilch/permission"
    snap = await fetch_snapshot(
        _api(FixtureTransport([574], extra={perm: {"permission": "admin"}})), 574, use_graphql=False
    )
    assert snap.author_permission == "admin"
    missing = await fetch_snapshot(_api(FixtureTransport([574])), 574, use_graphql=False)
    assert missing.author_permission is None


async def test_stack_drift_from_compare():
    compare = f"GET {BASE}/compare/feat/sleep-timer-backend...feat/sleep-timer-frontend"
    transport = FixtureTransport([574], extra={compare: {"behind_by": 3}})
    heads = frozenset({"feat/sleep-timer-backend"})
    snap = await fetch_snapshot(_api(transport), 574, use_graphql=False, open_pr_heads=heads)
    assert snap.stack_drift == 3
    # base is not another PR's head, or heads unknown: no drift information
    other = await fetch_snapshot(_api(FixtureTransport([574])), 574, use_graphql=False, open_pr_heads=frozenset())
    assert other.stack_drift is None
    on_main = await fetch_snapshot(
        _api(FixtureTransport([560])), 560, use_graphql=False, open_pr_heads=frozenset({"main2"})
    )
    assert on_main.stack_drift is None


async def test_threads_use_graphql():
    graphql = {
        "POST /graphql": {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {"nodes": [{"isResolved": False}, {"isResolved": True}, {"isResolved": False}]}
                    }
                }
            }
        }
    }
    transport = FixtureTransport([574], extra=graphql)
    snap = await fetch_snapshot(_api(transport), 574)
    assert snap.unresolved_threads == 2
    off = await fetch_snapshot(_api(FixtureTransport([574])), 574, use_graphql=False)
    assert off.unresolved_threads == -1
