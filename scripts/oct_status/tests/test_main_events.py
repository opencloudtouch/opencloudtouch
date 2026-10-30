"""Tests for the event pipeline: artifact resolution, fan-out, shadow mode, check and audit."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import pytest

from oct_status import main
from oct_status.api import GitHubApi
from oct_status.apply import MARKER
from oct_status.config import Actor, Config
from oct_status.main import resolve_artifact, run_audit, run_check, run_event

from .conftest import FixtureTransport

REPO = "o/r"
ROOT = f"/repos/{REPO}"
BOT = "oct-support"
CFG = Config(
    automation={BOT: Actor(BOT, "automation"), "dependabot[bot]": Actor("dependabot[bot]", "automation")},
    gate_checks=[],
    protected_paths=[],
    fan_out_cap=25,
    bot_logins=(BOT, "github-actions[bot]"),
)
CFG_DEPENDABOT = Config(
    automation={
        BOT: Actor(BOT, "automation"),
        "dependabot[bot]": Actor("dependabot[bot]", "automation", block_location="comment"),
    },
    gate_checks=[],
    protected_paths=[],
    bot_logins=(BOT, "github-actions[bot]"),
)
HUMAN = {"login": "alice"}


async def _nosleep(_: float) -> None:
    return None


class FakeRepo:
    """In-memory repository that only knows issues (no pull requests)."""

    def __init__(self) -> None:
        self.issues: dict[int, dict[str, Any]] = {}
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.writes: list[tuple[str, str]] = []
        self._next = 1000

    def add(self, number: int, body: str = "", labels: tuple[str, ...] = (), state: str = "open") -> None:
        self.issues[number] = {
            "number": number,
            "title": f"Issue {number}",
            "body": body,
            "state": state,
            "user": {"login": "reporter"},
            "labels": [{"name": n} for n in labels],
        }

    def label_names(self, number: int) -> set[str]:
        return {lb["name"] for lb in self.issues[number]["labels"]}

    def written_numbers(self, method: str, suffix: str = "") -> set[int]:
        out = set()
        for m, path in self.writes:
            hit = re.fullmatch(rf"{re.escape(ROOT)}/issues/(\d+){suffix}", path)
            if m == method and hit:
                out.add(int(hit[1]))
        return out

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        method = request.method
        body = json.loads(request.content) if request.content else {}
        if method != "GET" and not path.endswith("/graphql"):  # GraphQL queries are reads
            self.writes.append((method, path))
        if not path.startswith(ROOT):
            return httpx.Response(404, json={})
        rel = path[len(ROOT) :]
        page = request.url.params.get("page", "1")
        if rel == "/pulls" and method == "GET":
            return httpx.Response(200, json=[])
        if rel == "/issues" and method == "GET":
            open_ = [i for i in self.issues.values() if i["state"] == "open"]
            return httpx.Response(200, json=open_ if page == "1" else [])
        if (m := re.fullmatch(r"/issues/(\d+)", rel)) and int(m[1]) in self.issues:
            issue = self.issues[int(m[1])]
            if method == "PATCH":
                issue["body"] = body["body"]
            return httpx.Response(200, json=issue)
        if m := re.fullmatch(r"/issues/(\d+)/comments", rel):
            comments = self.comments.setdefault(int(m[1]), [])
            if method == "POST":
                self._next += 1
                comments.append({"id": self._next, "body": body["body"], "user": {"login": BOT}})
                return httpx.Response(201, json={"id": self._next})
            return httpx.Response(200, json=comments if page == "1" else [])
        if m := re.fullmatch(r"/issues/comments/(\d+)", rel):
            for comments in self.comments.values():
                for c in comments:
                    if c["id"] == int(m[1]):
                        if method == "PATCH":
                            c["body"] = body["body"]
                        return httpx.Response(200, json=c)
        if (m := re.fullmatch(r"/issues/(\d+)/labels", rel)) and method == "POST":
            number = int(m[1])
            have = self.label_names(number)
            self.issues[number]["labels"] += [{"name": n} for n in body["labels"] if n not in have]
            return httpx.Response(200, json=[])
        if m := re.fullmatch(r"/issues/(\d+)/labels/(.+)", rel):
            number = int(m[1])
            self.issues[number]["labels"] = [lb for lb in self.issues[number]["labels"] if lb["name"] != m[2]]
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"message": "Not Found"})


def api_for(transport: httpx.MockTransport | FakeRepo, repo: str = REPO) -> GitHubApi:
    if isinstance(transport, FakeRepo):
        transport = httpx.MockTransport(transport.handler)
    return GitHubApi("secret-token-value", repo, transport=transport, sleep=_nosleep)


def issue_event(number: int, action: str = "opened", sender: dict | None = None) -> dict:
    return {"action": action, "issue": {"number": number}, "sender": sender or HUMAN}


@pytest.fixture
def summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    return path


def stack(repo: FakeRepo, first: int, count: int) -> None:
    repo.add(first)
    for n in range(first + 1, first + count):
        repo.add(n, body=f"Depends on #{n - 1}")


# --- artifact resolution ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "payload", "expected"),
    [
        ("issues", {"issue": {"number": 7}}, 7),
        ("issue_comment", {"issue": {"number": 8}, "comment": {"body": "x"}}, 8),
        ("pull_request_target", {"pull_request": {"number": 9}}, 9),
        ("pull_request_review", {"pull_request": {"number": 10}}, 10),
        ("pull_request_review_comment", {"pull_request": {"number": 11}}, 11),
        ("discussion", {"discussion": {"number": 12}}, 12),
        ("discussion_comment", {"discussion": {"number": 13}}, 13),
        ("check_suite", {"check_suite": {"pull_requests": [{"number": 14}], "head_sha": "a" * 40}}, 14),
        ("schedule", {}, None),
        ("issues", {}, None),
        ("issues", {"issue": {"number": "not-a-number"}}, None),
    ],
)
async def test_event_resolves_artifact_number(event, payload, expected):
    api = api_for(FixtureTransport())
    assert await resolve_artifact(api, event, payload) == expected
    await api.aclose()


async def test_check_suite_maps_head_sha_to_pull_request():
    sha = "5f26740dc92e1be1664edc3970a7b20c6a5f7990"
    transport = FixtureTransport(extra={f"GET {ROOT}/commits/{sha}/pulls": [{"number": 560, "state": "open"}]})
    api = api_for(transport)
    payload = {"check_suite": {"pull_requests": [], "head_sha": sha}}
    assert await resolve_artifact(api, "check_suite", payload) == 560
    await api.aclose()


async def test_check_suite_without_pull_request_or_with_hostile_sha():
    transport = FixtureTransport(extra={f"GET {ROOT}/commits/{'b' * 40}/pulls": []})
    api = api_for(transport)
    assert await resolve_artifact(api, "check_suite", {"check_suite": {"head_sha": "b" * 40}}) is None
    before = len(transport.requests)
    assert await resolve_artifact(api, "check_suite", {"check_suite": {"head_sha": "../../x"}}) is None
    assert len(transport.requests) == before  # never interpolated into a path
    await api.aclose()


# --- loop guard ---------------------------------------------------------------------------------


async def test_own_event_exits_early_without_requests():
    transport = FixtureTransport()
    api = api_for(transport)
    event = issue_event(5, "edited", sender={"login": BOT})
    assert await run_event(api, CFG, "issues", event, dry_run=False) == 0
    assert transport.requests == []
    await api.aclose()


# --- fan-out ------------------------------------------------------------------------------------


async def test_fan_out_limited_to_component_and_cap():
    repo = FakeRepo()
    stack(repo, 560, 1)
    stack(repo, 570, 5)
    repo.issues[570]["body"] = "Depends on #560"
    repo.add(600, body="unrelated")
    api = api_for(repo)
    assert await run_event(api, CFG, "issues", issue_event(560), dry_run=False) == 0
    assert repo.written_numbers("PATCH") == {560, 570, 571, 572, 573, 574}
    assert 600 not in repo.written_numbers("PATCH") | repo.written_numbers("POST", "/comments")
    await api.aclose()


async def test_fan_out_cap_processes_25_of_40():
    repo = FakeRepo()
    stack(repo, 100, 40)
    api = api_for(repo)
    assert await run_event(api, CFG, "issues", issue_event(100), dry_run=False) == 0
    patched = repo.written_numbers("PATCH")
    assert len(patched) == 25
    assert 100 in patched
    await api.aclose()


async def test_missing_artifact_is_skipped():
    repo = FakeRepo()
    api = api_for(repo)
    assert await run_event(api, CFG, "issues", issue_event(404), dry_run=False) == 0
    assert repo.writes == []
    await api.aclose()


async def test_dangling_reference_does_not_break_the_walk(summary):
    repo = FakeRepo()
    repo.add(1, body="Depends on #999 and see Closes #abc")
    api = api_for(repo)
    assert await run_event(api, CFG, "issues", issue_event(1), dry_run=True) == 0
    assert "closes #abc" in summary.read_text().lower()  # unresolved reference surfaced
    await api.aclose()


async def test_discussion_events_are_not_handled_yet():
    repo = FakeRepo()
    api = api_for(repo)
    event = {"action": "created", "discussion": {"number": 3}, "sender": HUMAN}
    assert await run_event(api, CFG, "discussion", event, dry_run=False) == 0
    assert repo.writes == []
    await api.aclose()


async def test_announcement_writes_nothing():
    repo = FakeRepo()
    repo.add(2)
    repo.issues[2]["user"] = {"login": "dependabot[bot]"}
    api = api_for(repo)
    assert await run_event(api, CFG, "issues", issue_event(2), dry_run=False) == 0
    assert repo.writes == []
    await api.aclose()


# --- shadow mode ----------------------------------------------------------------------------------


async def test_shadow_mode_writes_only_job_summary(summary):
    repo_name = "opencloudtouch/opencloudtouch"
    root = f"/repos/{repo_name}"
    transport = FixtureTransport(
        [560],
        extra={f"GET {root}/pulls": [], f"GET {root}/issues": [], f"GET {root}/issues/560/comments": []},
    )
    api = api_for(transport, repo_name)
    event = {"action": "synchronize", "pull_request": {"number": 560}, "sender": HUMAN}
    assert await run_event(api, CFG, "pull_request_target", event, dry_run=True) == 0
    await api.aclose()
    writes = [r for r in transport.requests if not r.startswith("GET ") and r != "POST /graphql"]
    assert writes == []
    text = summary.read_text()
    assert "<!-- oct-status:v1" in text
    assert "dry-run" in text
    assert "add labels" in text
    assert "secret-token-value" not in text


async def test_dry_run_on_issue_plans_but_does_not_write(summary):
    repo = FakeRepo()
    repo.add(1)
    api = api_for(repo)
    assert await run_event(api, CFG, "issues", issue_event(1), dry_run=True) == 0
    assert repo.writes == []
    assert "guide comment created" in summary.read_text()
    await api.aclose()


async def test_real_run_converges_and_second_run_is_silent():
    repo = FakeRepo()
    repo.add(1)
    api = api_for(repo)
    await run_event(api, CFG, "issues", issue_event(1), dry_run=False)
    assert any(n.startswith("phase:") for n in repo.label_names(1))
    assert "<!-- oct-status:v1" in repo.issues[1]["body"]
    assert len(repo.comments[1]) == 1
    assert repo.comments[1][0]["body"].count(MARKER) == 1
    repo.writes.clear()
    await run_event(api, CFG, "issues", issue_event(1, "edited"), dry_run=False)
    assert repo.writes == []
    await api.aclose()


# --- check mode -----------------------------------------------------------------------------------


async def test_check_mode_exit_codes():
    repo = FakeRepo()
    repo.add(1, body="intro")
    api = api_for(repo)
    assert await run_check(api, CFG, "issues", issue_event(1)) == 1  # block missing
    await run_event(api, CFG, "issues", issue_event(1), dry_run=False)
    assert await run_check(api, CFG, "issues", issue_event(1)) == 0
    repo.issues[1]["body"] = repo.issues[1]["body"].replace("**Root blocker:** none", "**Root blocker:** #9")
    assert await run_check(api, CFG, "issues", issue_event(1)) == 1  # stale block
    await api.aclose()


async def test_check_mode_without_artifact_or_for_announcement_is_healthy():
    repo = FakeRepo()
    repo.add(2)
    repo.issues[2]["user"] = {"login": "dependabot[bot]"}
    api = api_for(repo)
    assert await run_check(api, CFG, "schedule", {}) == 0
    assert await run_check(api, CFG, "issues", issue_event(2)) == 0
    assert await run_check(api, CFG, "issues", issue_event(404)) == 0
    await api.aclose()


async def test_check_mode_reads_pinned_comment_for_dependency_prs():
    repo_name = "opencloudtouch/opencloudtouch"
    root = f"/repos/{repo_name}"
    stored: list[dict] = []

    def post_comment(request: httpx.Request):
        stored.append({"id": 1, "body": json.loads(request.content)["body"], "user": {"login": BOT}})
        return {"id": 1}

    transport = FixtureTransport(
        [498],
        extra={
            f"GET {root}/pulls": [],
            f"GET {root}/issues": [],
            f"GET {root}/issues/498/comments": lambda request: stored,
            f"POST {root}/issues/498/comments": post_comment,
            f"POST {root}/issues/498/labels": [],
        },
    )
    api = api_for(transport, repo_name)
    event = {"action": "synchronize", "pull_request": {"number": 498}, "sender": HUMAN}
    assert await run_check(api, CFG_DEPENDABOT, "pull_request_target", event) == 1  # pinned comment missing
    await run_event(api, CFG_DEPENDABOT, "pull_request_target", event, dry_run=False)
    assert stored and stored[0]["body"].count(MARKER) == 1
    assert await run_check(api, CFG_DEPENDABOT, "pull_request_target", event) == 0
    await api.aclose()


# --- audit ----------------------------------------------------------------------------------------


async def test_audit_heals_drift_on_all_open_artifacts(summary):
    repo = FakeRepo()
    for n in (1, 2, 3):
        repo.add(n, body=f"body {n}")
    repo.add(4, state="closed")
    api = api_for(repo)
    assert await run_audit(api, CFG, dry_run=False) == 3  # first run creates everything
    assert repo.written_numbers("PATCH") == {1, 2, 3}
    repo.issues[1]["body"] = "body 1"  # block lost
    repo.issues[2]["labels"] = [{"name": "wait:ci"}]  # wrong fact label
    repo.writes.clear()
    assert await run_audit(api, CFG, dry_run=False) == 2
    assert repo.written_numbers("PATCH") == {1}
    assert "wait:ci" not in repo.label_names(2)
    assert not any(path.endswith("/issues/3") or "/issues/3/" in path for _, path in repo.writes)
    assert "repaired 2" in summary.read_text()
    await api.aclose()


async def test_audit_dry_run_reports_without_writing(summary):
    repo = FakeRepo()
    repo.add(1)
    api = api_for(repo)
    assert await run_audit(api, CFG, dry_run=True) == 1
    assert repo.writes == []
    assert "dry-run" in summary.read_text()
    await api.aclose()


# --- CLI ------------------------------------------------------------------------------------------


@pytest.fixture
def cli_repo(monkeypatch: pytest.MonkeyPatch) -> FakeRepo:
    repo = FakeRepo()

    def factory(token: str, name: str, **kw: Any) -> GitHubApi:
        return GitHubApi(token, name, transport=httpx.MockTransport(repo.handler), sleep=_nosleep, **kw)

    monkeypatch.setattr(main, "GitHubApi", factory)
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token-value")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.delenv("BOT_PAT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return repo


def payload_file(tmp_path: Path, data: Any) -> str:
    path = tmp_path / "event.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(path)


def test_cli_event_dry_run(cli_repo, tmp_path, capsys):
    cli_repo.add(1)
    args = ["--event", "issues", "--payload", payload_file(tmp_path, issue_event(1)), "--dry-run"]
    assert main.cli(args) == 0
    assert cli_repo.writes == []
    assert "secret-token-value" not in capsys.readouterr().out


def test_cli_event_real_run_writes(cli_repo, tmp_path):
    cli_repo.add(1)
    assert main.cli(["--event", "issues", "--payload", payload_file(tmp_path, issue_event(1))]) == 0
    assert cli_repo.writes


def test_cli_stdout_never_echoes_artifact_text(cli_repo, tmp_path, capsys):
    cli_repo.add(1, body="::error::injected\nDepends on #2")
    cli_repo.issues[1]["title"] = "::set-output name=x::y"
    assert main.cli(["--event", "issues", "--payload", payload_file(tmp_path, issue_event(1)), "--dry-run"]) == 0
    assert "::" not in capsys.readouterr().out


def test_cli_check_exit_codes(cli_repo, tmp_path):
    cli_repo.add(1)
    args = ["--check", "--event", "issues", "--payload", payload_file(tmp_path, issue_event(1))]
    assert main.cli(args) == 1
    assert main.cli(args[1:]) == 0
    assert main.cli(args) == 0


def test_cli_audit(cli_repo, capsys):
    cli_repo.add(1)
    assert main.cli(["--audit", "--dry-run"]) == 0
    assert cli_repo.writes == []
    assert "1" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["--event", "issues"],
        ["--payload", "x.json"],
        ["--check"],
        ["--check", "--event", "issues"],
        ["--event", "issues", "--payload", "/nonexistent/event.json"],
    ],
)
def test_cli_bad_arguments_exit_two(cli_repo, argv):
    assert main.cli(argv) == 2


def test_cli_rejects_invalid_or_non_object_payload(cli_repo, tmp_path):
    assert main.cli(["--event", "issues", "--payload", payload_file(tmp_path, "{not json")]) == 2
    assert main.cli(["--event", "issues", "--payload", payload_file(tmp_path, "[1]")]) == 2


def test_cli_api_failure_exits_one(cli_repo, tmp_path, monkeypatch):
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    cli_repo.handler = failing  # type: ignore[method-assign]
    cli_repo.add(1)
    assert main.cli(["--audit", "--dry-run"]) == 1


# --- read-only API, truncation -----------------------------------------------------------------


@pytest.mark.parametrize("method", ["PATCH", "POST", "DELETE", "PUT"])
async def test_read_only_api_refuses_writes(method):
    from oct_status.api import ReadOnlyError

    repo = FakeRepo()
    api = GitHubApi("t", REPO, transport=httpx.MockTransport(repo.handler), sleep=_nosleep, read_only=True)
    with pytest.raises(ReadOnlyError):
        await api.request(method, "/issues/1", json={"body": "x"})
    with pytest.raises(ReadOnlyError):
        await api.graphql("mutation { x }", {})
    assert repo.writes == []
    await api.aclose()


async def test_read_only_api_allows_get_and_graphql_query():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200, json={"data": {"ok": 1}})

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(handler), sleep=_nosleep, read_only=True)
    assert (await api.request("GET", "/labels")).status_code == 200
    assert await api.graphql("query { x }", {}) == {"ok": 1}
    assert seen == ["GET", "POST"]
    await api.aclose()


async def test_event_and_audit_run_through_read_only_api(summary):
    repo = FakeRepo()
    stack(repo, 10, 3)
    api = GitHubApi("t", REPO, transport=httpx.MockTransport(repo.handler), sleep=_nosleep, read_only=True)
    assert await run_event(api, CFG, "issues", issue_event(10), dry_run=True) == 0
    assert await run_audit(api, CFG, dry_run=True) == 3
    assert await run_check(api, CFG, "issues", issue_event(10)) == 1
    assert repo.writes == []
    await api.aclose()


async def test_truncated_listing_warns_and_audit_never_writes(summary, monkeypatch):
    monkeypatch.setattr(main, "_MAX_PAGES", 1)
    monkeypatch.setattr(main, "_PER_PAGE", 1)
    repo = FakeRepo()
    repo.add(1)
    repo.add(2)
    api = api_for(repo)
    assert await run_audit(api, CFG, dry_run=False) == 2
    assert repo.writes == []
    text = summary.read_text()
    assert "cut off" in text
    assert "forced to dry-run" in text
    await api.aclose()


def test_cli_dry_run_uses_read_only_api(monkeypatch, cli_repo, tmp_path):
    seen: list[bool] = []
    orig = main.GitHubApi

    def spy(token, name, **kw):
        api = orig(token, name, **kw)
        seen.append(api.read_only)
        return api

    cli_repo.add(1)
    monkeypatch.setattr(main, "GitHubApi", spy)
    args = ["--event", "issues", "--payload", payload_file(tmp_path, issue_event(1))]
    assert main.cli([*args, "--dry-run"]) == 0
    assert main.cli(args) == 0
    assert seen == [True, False]


class TrackingRepo(FakeRepo):
    """FakeRepo whose issue 50 tracks 51 and 52 as native sub-issues."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == f"{ROOT}/issues/50/sub_issues":
            return httpx.Response(200, json=[{"number": 51}, {"number": 52}])
        return super().handler(request)


async def test_fan_out_follows_propagating_edges_only():
    from oct_status.graph import walk_component
    from oct_status.main import Workspace

    repo = TrackingRepo()
    repo.add(50)
    repo.issues[50]["title"] = "[Tracking] all of it"
    repo.add(51)
    repo.add(52)
    api = api_for(repo)
    await run_event(api, CFG, "issues", issue_event(50), dry_run=False)
    assert repo.written_numbers("PATCH") == {50}  # children are read for the phase, not rewritten
    ws = Workspace(api, CFG)
    await ws.load(50)
    # Up from a child to its tracking issue, never back down to the sibling.
    assert await walk_component(51, ws.fan_out, 25) == {50, 51}
    await api.aclose()
