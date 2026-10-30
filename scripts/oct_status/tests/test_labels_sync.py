"""Tests for the idempotent label sync against an in-memory fake GitHub."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

from oct_status.api import GitHubApi
from oct_status.labels_sync import LedgerIssueError, ensure_ledger_issue, sync_labels

SPEC = Path(__file__).resolve().parent.parent / "labels.yml"
REPO = "o/r"
ROOT = f"/repos/{REPO}"


class FakeGitHub:
    def __init__(self, labels: dict[str, dict] | None = None) -> None:
        self.labels = labels or {}
        self.issues: list[dict] = []
        self.writes: list[tuple[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        method = request.method
        body = json.loads(request.content) if request.content else {}
        if method != "GET":
            self.writes.append((method, path))
        if path == f"{ROOT}/labels" and method == "GET":
            page = int(request.url.params.get("page", "1"))
            items = list(self.labels.values())
            return httpx.Response(200, json=items if page == 1 else [])
        if path == f"{ROOT}/labels" and method == "POST":
            self.labels[body["name"]] = {
                "name": body["name"],
                "color": body["color"],
                "description": body.get("description", ""),
            }
            return httpx.Response(201, json=self.labels[body["name"]])
        if path.startswith(f"{ROOT}/labels/") and method == "PATCH":
            old = path[len(f"{ROOT}/labels/") :]
            label = self.labels.pop(old)
            label.update({k: v for k, v in body.items() if k != "new_name"})
            label["name"] = body.get("new_name", old)
            self.labels[label["name"]] = label
            return httpx.Response(200, json=label)
        if path == f"{ROOT}/issues" and method == "GET":
            page = int(request.url.params.get("page", "1"))
            wanted = request.url.params.get("labels")
            items = [i for i in self.issues if not wanted or wanted in i.get("labels", [])]
            return httpx.Response(200, json=items if page == 1 else [])
        if (m := re.fullmatch(rf"{ROOT}/issues/(\d+)/labels", path)) and method == "POST":
            issue = next(i for i in self.issues if i["number"] == int(m[1]))
            issue.setdefault("labels", [])
            issue["labels"] += [x for x in body["labels"] if x not in issue["labels"]]
            return httpx.Response(200, json=[])
        if (m := re.fullmatch(rf"{ROOT}/issues/(\d+)/labels/(.+)", path)) and method == "DELETE":
            issue = next(i for i in self.issues if i["number"] == int(m[1]))
            issue["labels"].remove(m[2])
            return httpx.Response(200, json=[])
        if path.startswith(f"{ROOT}/labels/") and method == "DELETE":
            del self.labels[path[len(f"{ROOT}/labels/") :]]
            return httpx.Response(204)
        if path == f"{ROOT}/issues" and method == "POST":
            issue = {
                "number": len(self.issues) + 1,
                "title": body["title"],
                "body": body.get("body", ""),
                "locked": False,
            }
            self.issues.append(issue)
            return httpx.Response(201, json=issue)
        if (m := re.fullmatch(rf"{ROOT}/issues/(\d+)", path)) and method == "GET":
            found = [i for i in self.issues if i["number"] == int(m[1])]
            return httpx.Response(200, json=found[0]) if found else httpx.Response(404, json={})
        if path.endswith("/lock") and method == "PUT":
            number = int(path.split("/")[-2])
            self.issues[number - 1]["locked"] = True
            return httpx.Response(204)
        return httpx.Response(404, json={"message": "not found"})


def make(labels: dict[str, dict] | None = None) -> tuple[FakeGitHub, GitHubApi]:
    fake = FakeGitHub(labels)

    async def no_sleep(_: float) -> None:
        return None

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(fake.handler), sleep=no_sleep)
    return fake, api


def lab(name: str, color: str = "ededed", description: str = "") -> dict:
    return {"name": name, "color": color, "description": description}


async def test_renames_legacy_labels():
    legacy = ["wip", "needs-info", "blocked", "accepted", "duplicate", "wontfix", "invalid"]
    fake, api = make({n: lab(n) for n in legacy})
    await sync_labels(api, SPEC)
    for new in [
        "phase:in-progress",
        "wait:reporter",
        "wait:prerequisite",
        "phase:triaged",
        "resolution:duplicate",
        "resolution:wontfix",
        "resolution:invalid",
    ]:
        assert new in fake.labels
    assert not set(legacy) & set(fake.labels)
    assert ("PATCH", f"{ROOT}/labels/wip") in fake.writes
    assert not any(m == "DELETE" for m, _ in fake.writes)


async def test_creates_missing_with_colors():
    fake, api = make()
    await sync_labels(api, SPEC)
    expected = {
        "phase:in-review": "2a5cc0",
        "phase:verification": "1e4590",
        "phase:done": "1a7f37",
        "wait:ci": "f2a33a",
        "resolution:superseded": "c9d1d9",
    }
    for name, color in expected.items():
        assert fake.labels[name]["color"] == color


async def test_recolors():
    fake, api = make({"spec": lab("spec", "000000", "Spec"), "enhancement": lab("enhancement", "000000", "Enh")})
    await sync_labels(api, SPEC)
    assert fake.labels["spec"]["color"] == "8250df"
    assert fake.labels["enhancement"]["color"] == "b8f0c6"
    assert fake.labels["spec"]["description"] == "Spec"
    assert fake.labels["enhancement"]["description"] == "Enh"


async def test_leaves_foreign_labels():
    foreign = ["prio:0", "priority: low", "review", "gitar-approved", "dependencies"]
    fake, api = make({n: lab(n, "123456", "x") for n in foreign})
    await sync_labels(api, SPEC)
    for n in foreign:
        assert fake.labels[n] == lab(n, "123456", "x")
        assert not any(p.endswith("/" + n) for _, p in fake.writes)


async def test_second_run_is_noop():
    fake, api = make({"wip": lab("wip")})
    first = await sync_labels(api, SPEC)
    assert first
    fake.writes.clear()
    assert await sync_labels(api, SPEC) == []
    assert fake.writes == []


async def test_dry_run_writes_nothing():
    fake, api = make({"wip": lab("wip")})
    ops = await sync_labels(api, SPEC, dry_run=True)
    assert ops
    assert fake.writes == []
    assert "wip" in fake.labels


async def test_ledger_issue_created_once_and_locked():
    fake, api = make()
    first = await ensure_ledger_issue(api)
    assert first > 0
    assert fake.issues[0]["title"] == "oct-status ledger"
    assert "machine-written" in fake.issues[0]["body"]
    assert fake.issues[0]["locked"] is True
    fake.writes.clear()
    assert await ensure_ledger_issue(api) == first
    assert fake.writes == []
    assert len(fake.issues) == 1


async def test_ledger_dry_run():
    fake, api = make()
    assert await ensure_ledger_issue(api, dry_run=True) == 0
    assert fake.writes == []


async def test_retry_on_5xx_then_success_honours_retry_after():
    calls: list[int] = []
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(503)
        if len(calls) == 2:
            return httpx.Response(429, headers={"retry-after": "7"})
        return httpx.Response(200, json=[])

    async def sleep(s: float) -> None:
        slept.append(s)

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(handler), sleep=sleep)
    resp = await api.request("GET", "/labels")
    assert resp.status_code == 200
    assert len(calls) == 3
    assert 1 <= slept[0] <= 1.5
    assert slept[1] == 7


async def test_retry_gives_up_after_max_and_403_without_ratelimit_is_final():
    n = {"c": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["c"] += 1
        return httpx.Response(500)

    async def sleep(_: float) -> None:
        return None

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(handler), sleep=sleep)
    assert (await api.request("GET", "/x")).status_code == 500
    assert n["c"] == 4

    n["c"] = 0

    def forbidden(request: httpx.Request) -> httpx.Response:
        n["c"] += 1
        return httpx.Response(403)

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(forbidden), sleep=sleep)
    assert (await api.request("GET", "/x")).status_code == 403
    assert n["c"] == 1


async def test_403_with_ratelimit_retries_and_absolute_and_graphql_paths():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/graphql":
            return httpx.Response(200, json={"data": {"x": 1}})
        if len(seen) == 1:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
        return httpx.Response(200, json={})

    async def sleep(_: float) -> None:
        return None

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(handler), sleep=sleep)
    await api.request("GET", "/repos/other/x/issues")
    assert seen == ["/repos/other/x/issues", "/repos/other/x/issues"]
    assert await api.graphql("query { x }", {}) == {"x": 1}


async def test_graphql_errors_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "boom"}]})

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError):
        await api.graphql("query { x }", {})


async def test_existing_unlocked_ledger_issue_gets_locked():
    fake, api = make()
    fake.issues.append({"number": 1, "title": "oct-status ledger", "body": "x", "locked": False})
    assert await ensure_ledger_issue(api, dry_run=True) == 1
    assert fake.writes == []
    assert await ensure_ledger_issue(api) == 1
    assert fake.issues[0]["locked"] is True
    fake.writes.clear()
    assert await ensure_ledger_issue(api) == 1
    assert fake.writes == []


def test_labels_yml_matches_enums():
    import yaml

    from oct_status.model import Phase, Resolution, Wait

    names = {e["name"] for e in yaml.safe_load(SPEC.read_text(encoding="utf-8"))["labels"]}
    for prefix, enum in (("phase:", Phase), ("wait:", Wait), ("resolution:", Resolution)):
        assert {n for n in names if n.startswith(prefix)} == {m.label for m in enum}


async def test_ledger_issue_by_a_stranger_is_ignored_and_configured_number_is_verified():
    bots = ("oct-support", "github-actions[bot]")

    def planted(login: str, **extra) -> tuple[FakeGitHub, GitHubApi]:
        fake, api = make()
        fake.issues.append(
            {"number": 1, "title": "oct-status ledger", "locked": True, "user": {"login": login}, **extra}
        )
        return fake, api

    _, api = planted("mallory")
    assert await ensure_ledger_issue(api, dry_run=True, bot_logins=bots) == 0  # planted look-alike ignored
    fake, api = planted("mallory")
    assert await ensure_ledger_issue(api, bot_logins=bots) == 2  # a real one is created instead
    _, api = planted("oct-support")
    assert await ensure_ledger_issue(api, dry_run=True, bot_logins=bots) == 1
    # A configured number is checked with one request and then used without a search.
    fake, api = planted("oct-support")
    assert await ensure_ledger_issue(api, bot_logins=bots, configured=1) == 1
    assert fake.writes == []
    for bad in (planted("mallory"), planted("oct-support", pull_request={})):
        with pytest.raises(LedgerIssueError):
            await ensure_ledger_issue(bad[1], bot_logins=bots, configured=1)
    fake, api = planted("oct-support", locked=False)
    await ensure_ledger_issue(api, bot_logins=bots, configured=1)
    assert fake.writes == [("PUT", f"{ROOT}/issues/1/lock")]
    _, api = planted("oct-support")
    with pytest.raises(httpx.HTTPStatusError):
        await ensure_ledger_issue(api, bot_logins=bots, configured=42)  # does not exist


async def test_phase_confirmed_is_described_as_the_bug_phase_and_updated_once():
    """`confirmed` is the bug phase (`/oct confirm`); an outdated description is updated, then nothing."""
    fake, api = make({"phase:confirmed": lab("phase:confirmed", "7ba3ec", "Specification confirmed")})
    await sync_labels(api, SPEC)
    assert fake.labels["phase:confirmed"]["description"] == "Bug reproduced and confirmed by a maintainer"
    assert ("PATCH", f"{ROOT}/labels/phase:confirmed") in fake.writes
    fake.writes.clear()
    assert await sync_labels(api, SPEC) == []
    assert fake.writes == []


def labelled(fake: FakeGitHub, numbers: list[int], label: str) -> None:
    fake.issues += [{"number": n, "title": f"t{n}", "labels": [label]} for n in numbers]


async def test_migrates_items_when_legacy_and_new_label_both_exist():
    fake, api = make({"needs-info": lab("needs-info"), "wait:reporter": lab("wait:reporter")})
    labelled(fake, [5, 6, 7], "needs-info")
    ops = await sync_labels(api, SPEC)
    assert "needs-info" not in fake.labels and "wait:reporter" in fake.labels
    assert all(i["labels"] == ["wait:reporter"] for i in fake.issues)
    assert ("DELETE", f"{ROOT}/labels/needs-info") in fake.writes
    assert sum(op.startswith("move needs-info") for op in ops) == 3
    assert not any(m == "PATCH" and p.endswith("/labels/needs-info") for m, p in fake.writes)


async def test_migration_is_idempotent_for_items_already_carrying_the_new_label():
    fake, api = make({"needs-info": lab("needs-info"), "wait:reporter": lab("wait:reporter")})
    fake.issues.append({"number": 1, "title": "t", "labels": ["needs-info", "wait:reporter"]})
    await sync_labels(api, SPEC)
    assert fake.issues[0]["labels"] == ["wait:reporter"]


async def test_only_legacy_label_is_still_renamed_in_place():
    fake, api = make({"needs-info": lab("needs-info")})
    labelled(fake, [5], "needs-info")
    await sync_labels(api, SPEC)
    assert "wait:reporter" in fake.labels and "needs-info" not in fake.labels
    assert ("PATCH", f"{ROOT}/labels/needs-info") in fake.writes
    assert not any(m == "DELETE" for m, _ in fake.writes)
    assert not any(p.endswith("/issues/5/labels") for _, p in fake.writes)


async def test_only_new_label_needs_no_migration():
    fake, api = make({"wait:reporter": lab("wait:reporter")})
    ops = await sync_labels(api, SPEC)
    assert not any("needs-info" in op for op in ops)
    assert not any(m == "DELETE" for m, _ in fake.writes)


async def test_dry_run_plans_migration_without_writing():
    fake, api = make({"needs-info": lab("needs-info"), "wait:reporter": lab("wait:reporter")})
    labelled(fake, [5, 6, 7], "needs-info")
    ops = await sync_labels(api, SPEC, dry_run=True)
    assert sum(op.startswith("move needs-info") for op in ops) == 3
    assert any(op.startswith("delete needs-info") for op in ops)
    assert fake.writes == []
    assert all(i["labels"] == ["needs-info"] for i in fake.issues)


async def test_second_run_after_migration_is_a_noop():
    fake, api = make({"needs-info": lab("needs-info"), "wait:reporter": lab("wait:reporter")})
    labelled(fake, [5, 6], "needs-info")
    await sync_labels(api, SPEC)
    fake.writes.clear()
    ops = await sync_labels(api, SPEC)
    assert not any("needs-info" in op for op in ops)
    assert not any(m == "DELETE" for m, _ in fake.writes)


async def test_migration_retries_on_rate_limit():
    fake, api = make({"needs-info": lab("needs-info"), "wait:reporter": lab("wait:reporter")})
    labelled(fake, [5], "needs-info")
    orig = fake.handler
    state = {"limited": False}

    def limited(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/issues/5/labels") and not state["limited"]:
            state["limited"] = True
            return httpx.Response(403, headers={"retry-after": "1", "x-ratelimit-remaining": "0"})
        return orig(request)

    async def no_sleep(_: float) -> None:
        return None

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(limited), sleep=no_sleep)
    await sync_labels(api, SPEC)
    assert state["limited"] and fake.issues[0]["labels"] == ["wait:reporter"]
    assert "needs-info" not in fake.labels
