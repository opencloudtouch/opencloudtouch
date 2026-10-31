from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from oct_status.api import GitHubApi
from oct_status.facts import UNKNOWN_PATHS, fetch_snapshot

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


async def test_review_author_association_filled():
    # The recorded review fixtures carry no `author_association`; this route is synthetic.
    reviews = f"GET {BASE}/pulls/574/reviews"
    payload = [
        {"user": {"login": "bob"}, "state": "APPROVED", "commit_id": "abc", "author_association": "COLLABORATOR"},
        {"user": {"login": "eve"}, "state": "APPROVED", "commit_id": "abc"},
    ]
    snap = await fetch_snapshot(_api(FixtureTransport([574], extra={reviews: payload})), 574, use_graphql=False)
    assert [(r.user, r.author_association) for r in snap.reviews] == [("bob", "COLLABORATOR"), ("eve", "")]


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
        ],
        f"GET {BASE}/commits/b2": {"files": []},
        f"GET {BASE}/commits/c3": {"files": []},
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


async def test_commits_list_error_propagates():
    extra = {f"GET {BASE}/pulls/574/commits": (404, {"message": "Not Found"})}
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_snapshot(_api(FixtureTransport([574], extra=extra)), 574, use_graphql=False, cfg=_cfg())


async def test_commit_detail_error_propagates():
    extra = {f"GET {BASE}/pulls/574/commits": [_commit("c3", "gitar-bot[bot]")]}  # no /commits/c3 route -> 404
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_snapshot(_api(FixtureTransport([574], extra=extra)), 574, use_graphql=False, cfg=_cfg())


# Real response shapes of `GET /pulls/{n}/commits` recorded in the MA-8 experiment (PR #586).
def _gitar_commit(sha):
    return {
        "sha": sha,
        "author": {"login": "gitar-bot", "type": "User"},
        "committer": {"login": "gitar-bot", "type": "User"},
        "commit": {
            "author": {"name": "Gitar", "email": "noreply@gitar.ai"},
            "committer": {"name": "Gitar", "email": "noreply@gitar.ai"},
            "message": "fix(ci): pin action\n\nCo-authored-by: Someone <someone@example.org>",
        },
    }


def _formatter_commit(sha):
    return {
        "sha": sha,
        "author": None,
        "committer": None,
        "commit": {
            "author": {"name": "formatter-bot", "email": "noreply@opencloudtouch.org"},
            "committer": {"name": "formatter-bot", "email": "noreply@opencloudtouch.org"},
            "message": "style: format",
        },
    }


def _maintainer_commit(sha):
    return {
        "sha": sha,
        "author": {"login": "oct-support", "type": "User"},
        "committer": {"login": "oct-support", "type": "User"},
        "commit": {"author": {"name": "Maintainer", "email": "m@example.org"}, "message": "feat: x"},
    }


async def test_real_commit_shapes_from_the_gitar_experiment():
    from oct_status.rules import protected_changes

    extra = {
        f"GET {BASE}/pulls/574/commits": [_maintainer_commit("a1"), _gitar_commit("b2"), _formatter_commit("c3")],
        f"GET {BASE}/commits/a1": {"files": [{"filename": "must-not-be-read"}]},
        f"GET {BASE}/commits/b2": {"files": [{"filename": ".github/workflows/ci.yml"}]},
        f"GET {BASE}/commits/c3": {"files": [{"filename": "scripts/oct_status/rules.py"}]},
    }
    transport = FixtureTransport([574], extra=extra)
    cfg = _cfg()
    snap = await fetch_snapshot(_api(transport), 574, use_graphql=False, cfg=cfg)
    assert [(p.sha, p.author, p.committer) for p in snap.pushes] == [
        ("a1", "oct-support", "oct-support"),
        ("b2", "gitar-bot", "gitar-bot"),
        ("c3", "formatter-bot", ""),  # no login at all: the git author name is the fallback
    ]
    assert snap.pushes[0].paths == ()  # the maintainer's own commit: paths are not even read
    assert f"GET {BASE}/commits/a1" not in transport.requests
    open_pr = replace(snap, state="open", merged=False, head_sha="c3")
    assert protected_changes(open_pr, cfg) == [
        ("formatter-bot", "scripts/oct_status/rules.py"),
        ("gitar-bot", ".github/workflows/ci.yml"),
    ]


async def test_renamed_files_list_the_previous_path_too():
    """Moving a file OUT of a protected path touches that path."""
    files = [
        {"filename": "docs/ci.yml", "previous_filename": ".github/workflows/ci.yml", "status": "renamed"},
        {"filename": "a.py", "status": "modified"},
    ]
    extra = {
        f"GET {BASE}/pulls/574/commits": [_gitar_commit("b2")],
        f"GET {BASE}/commits/b2": {"files": files},
    }
    snap = await fetch_snapshot(_api(FixtureTransport([574], extra=extra)), 574, use_graphql=False, cfg=_cfg())
    assert snap.pushes[0].paths == ("docs/ci.yml", ".github/workflows/ci.yml", "a.py")


def _files_route(total):
    names = [f"f{i}.py" for i in range(total)]

    def route(request):
        page = int(request.url.params.get("page", "1"))
        return {"files": [{"filename": n} for n in names[(page - 1) * 100 : page * 100]]}

    return route


async def test_commit_files_are_paged():
    extra = {
        f"GET {BASE}/pulls/574/commits": [_commit("c3", "gitar-bot[bot]")],
        f"GET {BASE}/commits/c3": _files_route(140),
    }
    transport = FixtureTransport([574], extra=extra)
    snap = await fetch_snapshot(_api(transport), 574, use_graphql=False, cfg=_cfg())
    assert snap.pushes[0].paths == tuple(f"f{i}.py" for i in range(140))
    assert transport.requests.count(f"GET {BASE}/commits/c3") == 2


async def test_commit_files_limit_adds_unknown_sentinel():
    extra = {
        f"GET {BASE}/pulls/574/commits": [_commit("c3", "gitar-bot[bot]")],
        f"GET {BASE}/commits/c3": _files_route(3000),
    }
    snap = await fetch_snapshot(_api(FixtureTransport([574], extra=extra)), 574, use_graphql=False, cfg=_cfg())
    paths = snap.pushes[0].paths
    assert len(paths) == 3001
    assert paths[:3000] == tuple(f"f{i}.py" for i in range(3000))
    assert paths[-1] == UNKNOWN_PATHS


def _review(n: int, user: str, state: str = "COMMENTED") -> dict:
    return {"id": n, "user": {"login": user}, "state": state, "commit_id": "abc", "author_association": "MEMBER"}


def _paged_route(items: list[dict], key: str | None = None, link: bool = True):
    """A listing served 100 per page, with GitHub's Link header (rel="last") unless `link` is off."""
    seen: list[int] = []

    def route(request: httpx.Request) -> httpx.Response:
        page, size = int(request.url.params.get("page", "1")), int(request.url.params.get("per_page", "30"))
        seen.append(page)
        chunk = items[(page - 1) * size : page * size]
        last = max(1, -(-len(items) // size))
        headers = {"link": f'<https://api.github.com{request.url.path}?per_page={size}&page={last}>; rel="last"'}
        body = {"total_count": len(items), key: chunk} if key else chunk
        return httpx.Response(200, json=body, headers=headers if link and last > 1 else {})

    return route, seen


async def test_more_than_100_reviews_are_all_read_and_the_latest_verdict_counts():
    reviews = [_review(n, "bob") for n in range(150)] + [_review(150, "bob", "APPROVED")]
    route, seen = _paged_route(reviews)
    extra = {f"GET {BASE}/pulls/574/reviews": route}
    warnings: list[str] = []
    snap = await fetch_snapshot(_api(FixtureTransport([574], extra=extra)), 574, use_graphql=False, warnings=warnings)
    assert len(snap.reviews) == 151 and snap.reviews[-1].state == "APPROVED"
    assert sorted(seen) == [1, 2] and warnings == []


async def test_review_pages_beyond_the_cap_keep_the_newest_and_warn():
    from oct_status import facts

    reviews = [_review(n, f"u{n % 7}") for n in range(facts.MAX_LIST_PAGES * 100 + 250)]
    reviews[-1] = _review(len(reviews), "carol", "APPROVED")  # the newest review is on the last page
    route, seen = _paged_route(reviews)
    warnings: list[str] = []
    snap = await fetch_snapshot(
        _api(FixtureTransport([574], extra={f"GET {BASE}/pulls/574/reviews": route})),
        574,
        use_graphql=False,
        warnings=warnings,
    )
    assert len(seen) == facts.MAX_LIST_PAGES and max(seen) == facts.MAX_LIST_PAGES + 3
    assert snap.reviews[-1].user == "carol" and snap.reviews[-1].state == "APPROVED"
    assert warnings == [f"WARNING: reviews of #574 exceed {facts.MAX_LIST_PAGES} pages; only the newest are read"]


async def test_pages_without_link_header_are_followed_until_a_short_page():
    reviews = [_review(n, "bob") for n in range(230)]
    route, seen = _paged_route(reviews, link=False)
    snap = await fetch_snapshot(
        _api(FixtureTransport([574], extra={f"GET {BASE}/pulls/574/reviews": route})), 574, use_graphql=False
    )
    assert len(snap.reviews) == 230 and seen == [1, 2, 3]


async def test_more_than_100_check_runs_are_all_read():
    transport = FixtureTransport([574])
    sha = transport.routes[f"GET {BASE}/pulls/574"]["head"]["sha"]
    runs = [
        {"name": f"job {n}", "status": "completed", "conclusion": "success", "app": {"slug": "x"}} for n in range(140)
    ]
    runs.append({"name": "Gitar", "status": "completed", "conclusion": "failure", "app": {"slug": "gitar"}})
    route, seen = _paged_route(runs, key="check_runs")
    transport.routes[f"GET {BASE}/commits/{sha}/check-runs"] = route
    snap = await fetch_snapshot(_api(transport), 574, use_graphql=False)
    assert len(snap.checks) == 141 and snap.checks[-1].name == "Gitar" and sorted(seen) == [1, 2]
