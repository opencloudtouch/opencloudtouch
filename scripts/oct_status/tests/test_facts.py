from __future__ import annotations

from pathlib import Path

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


async def _no_sleep(_: float) -> None:
    return None


async def _assert_degraded(transport: httpx.AsyncBaseTransport) -> None:
    api = GitHubApi("t", REPO, transport=transport, sleep=_no_sleep)
    snap = await fetch_snapshot(api, 574)
    assert snap.unresolved_threads == -1
    assert snap.head_sha and snap.checks


async def test_graphql_http_error_degrades_to_unknown():
    await _assert_degraded(FixtureTransport([574], extra={"POST /graphql": (502, {"message": "bad gateway"})}))


async def test_graphql_transport_error_degrades_to_unknown():
    class Failing(FixtureTransport):
        def _handle(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/graphql":
                raise httpx.ConnectError("down", request=request)
            return super()._handle(request)

    await _assert_degraded(Failing([574]))


async def test_graphql_errors_payload_degrades_to_unknown():
    body = {"errors": [{"message": "boom"}], "data": None}
    await _assert_degraded(FixtureTransport([574], extra={"POST /graphql": body}))


async def test_graphql_null_pull_request_degrades_to_unknown():
    body = {"data": {"repository": {"pullRequest": None}}}
    await _assert_degraded(FixtureTransport([574], extra={"POST /graphql": body}))


# The endpoints below were never recorded; these tests use small synthetic `extra` routes.
def _commit(sha, login=None, committer=None, name="Some One"):
    return {
        "sha": sha,
        "author": {"login": login} if login else None,
        "committer": {"login": committer} if committer else None,
        "commit": {"author": {"name": name}},
    }


def _issue_objs(*numbers):
    return [{"number": n, "title": f"issue {n}"} for n in numbers]


def _cfg():
    from oct_status.config import load_config

    return load_config(Path(__file__).parent.parent / "config.yml")


async def test_pushes_from_pr_commits():
    extra = {
        f"GET {BASE}/pulls/574/commits": [
            _commit("a1", "scheilch"),
            _commit("b2", "formatter-bot"),
            _commit("c3", "gitar-bot[bot]"),
            _commit("d4", None, "committer-user"),
            _commit("e5", None, None, "Plain Name"),
        ]
    }
    snap = await fetch_snapshot(_api(FixtureTransport([574], extra=extra)), 574, use_graphql=False, cfg=_cfg())
    assert [(p.sha, p.author) for p in snap.pushes] == [
        ("a1", "scheilch"),
        ("b2", "formatter-bot"),
        ("c3", "gitar-bot[bot]"),
        ("d4", "committer-user"),
        ("e5", "Plain Name"),
    ]


async def test_paths_only_fetched_for_automation_authors():
    extra = {
        f"GET {BASE}/pulls/574/commits": [_commit("a1", "scheilch"), _commit("c3", "gitar-bot[bot]")],
        f"GET {BASE}/commits/c3": {"files": [{"filename": "a/b.py"}, {"filename": "c.md"}]},
        f"GET {BASE}/commits/a1": {"files": [{"filename": "must-not-be-read"}]},
    }
    transport = FixtureTransport([574], extra=extra)
    snap = await fetch_snapshot(_api(transport), 574, use_graphql=False, cfg=_cfg())
    assert snap.pushes[0].paths == ()
    assert snap.pushes[1].paths == ("a/b.py", "c.md")
    commit_requests = [r for r in transport.requests if r.startswith(f"GET {BASE}/commits/") and "check-runs" not in r]
    assert commit_requests == [f"GET {BASE}/commits/c3"]
    # without a config nobody counts as automation
    transport = FixtureTransport([574], extra=extra)
    bare = await fetch_snapshot(_api(transport), 574, use_graphql=False)
    assert all(p.paths == () for p in bare.pushes)
    assert f"GET {BASE}/commits/c3" not in transport.requests


async def test_sub_issues_and_blocked_by():
    extra = {
        f"GET {BASE}/issues/537/sub_issues": _issue_objs(540, 541),
        f"GET {BASE}/issues/537/dependencies/blocked_by": [],
    }
    snap = await fetch_snapshot(_api(FixtureTransport([537], extra=extra)), 537, use_graphql=False)
    assert snap.sub_issues == (540, 541)
    assert snap.blocked_by == ()
    extra = {f"GET {BASE}/issues/537/dependencies/blocked_by": _issue_objs(12)}
    snap = await fetch_snapshot(_api(FixtureTransport([537], extra=extra)), 537, use_graphql=False)
    assert snap.sub_issues == ()  # 404
    assert snap.blocked_by == (12,)


async def test_pushes_empty_for_issues():
    transport = FixtureTransport([537])
    snap = await fetch_snapshot(_api(transport), 537, use_graphql=False, cfg=_cfg())
    assert snap.pushes == ()
    assert not any("/commits" in r for r in transport.requests)
