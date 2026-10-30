"""Backfill: rate-limited, resumable migration of the existing open artifacts (no comments, no strikes)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

from oct_status import backfill as bf
from oct_status import main
from oct_status.api import GitHubApi
from oct_status.backfill import backfill, run_backfill

from .test_main_events import BOT, CFG, ROOT, FakeRepo, _nosleep, api_for
from .test_violations_events import ACTIVE, LEDGER, Repo, clock, run, seed

ISSUE = re.compile(rf"{ROOT}/(?:issues|pulls)/(\d+)(?:/.*)?$")


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class Limited:
    """Wraps a repo: every request about one artifact answers 403 with retry-after while `on`."""

    def __init__(self, repo: FakeRepo, number: int) -> None:
        self.repo, self.number, self.on = repo, number, True
        self.seen: list[int] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if m := ISSUE.match(request.url.path):
            self.seen.append(int(m[1]))
            if self.on and int(m[1]) == self.number:
                return httpx.Response(403, headers={"retry-after": "60"}, json={"message": "secondary rate limit"})
        return self.repo.handler(request)


class GraphqlRepo(FakeRepo):
    """FakeRepo whose label history query answers with no label events."""

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/graphql"):
            nodes: dict = {"timelineItems": {"nodes": []}}
            return httpx.Response(200, json={"data": {"repository": {"issueOrPullRequest": nodes}}})
        return super().handler(request)


def _api(handler) -> GitHubApi:
    return GitHubApi("t", "o/r", transport=httpx.MockTransport(handler), sleep=_nosleep)


def _state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def test_backfill_resumes_after_rate_limit(tmp_path):
    repo = FakeRepo()
    for n in range(1, 8):
        repo.add(n, body=f"issue {n}")
    limited = Limited(repo, 5)
    state = tmp_path / "state.json"
    api = _api(limited.handler)
    done = await backfill(api, CFG, list(range(1, 8)), state, clock, Sleeps())
    assert done == 4
    assert _state(state)["done"] == [1, 2, 3, 4]
    assert {1, 2, 3, 4} <= repo.written_numbers("PATCH") and 5 not in repo.written_numbers("PATCH")

    limited.on, limited.seen = False, []
    done = await backfill(api, CFG, list(range(1, 8)), state, clock, Sleeps())
    await api.aclose()
    assert done == 3
    assert not {1, 2, 3, 4} & set(limited.seen)  # nothing of the first batch is fetched again
    assert _state(state)["done"] == list(range(1, 8))


async def test_backfill_creates_no_guide_comments_and_no_strikes(tmp_path):
    repo = Repo()
    repo.add_pr(10)  # a pull request without a spec (V01 in an event run)
    repo.add(7, labels=("enhancement", "phase:done"))  # a hand-set fact label (V02 in an event run)
    seed(repo, "alice", [(1, "V01"), (2, "V01")])
    api = api_for(repo)
    assert await backfill(api, ACTIVE, [7, 10], tmp_path / "s.json", clock, Sleeps()) == 2
    await api.aclose()
    assert not [w for w in repo.writes if w[0] == "POST" and w[1].endswith("/comments")]
    assert not [w for w in repo.writes if "/issues/comments" in w[1]]  # no comment edited or deleted either
    assert len(repo.ledger()) == 2  # only the seeded entries
    assert "<!-- oct-status:v1" in repo.issues[10]["body"] and "<!-- oct-status:v1" in repo.issues[7]["body"]
    assert "phase:new" in repo.label_names(7) and "phase:done" not in repo.label_names(7)
    assert "phase:in-review" in repo.label_names(10)


async def test_backfill_sleeps_between_artifacts(tmp_path):
    repo = FakeRepo()
    for n in (1, 2, 3):
        repo.add(n)
    sleeps = Sleeps()
    api = api_for(repo)
    assert await backfill(api, CFG, [1, 2, 3], tmp_path / "s.json", clock, sleeps) == 3
    await api.aclose()
    assert len(sleeps.calls) == 2 and all(s >= bf.MIN_DELAY > 0 for s in sleeps.calls)


async def test_backfill_limit_dry_run_and_remaining(tmp_path, capsys, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = FakeRepo()
    for n in (1, 2, 3):
        repo.add(n)
    state = tmp_path / "s.json"
    api = api_for(repo)
    assert await run_backfill(api, CFG, state, limit=2, dry_run=True, clock=clock, sleep=Sleeps()) == 0
    assert repo.writes == [] and not state.exists()  # a dry run never marks anything as done
    assert "remaining: 3" in capsys.readouterr().out
    assert await run_backfill(api, CFG, state, limit=2, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    assert "remaining: 1" in capsys.readouterr().out and _state(state)["done"] == [1, 2]
    assert await run_backfill(api, CFG, state, limit=2, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    assert "remaining: 0" in capsys.readouterr().out
    await api.aclose()
    assert "remaining: 0" in summary.read_text(encoding="utf-8")


async def test_rate_limit_is_reported_with_the_wait_time(tmp_path, capsys):
    repo = FakeRepo()
    repo.add(1)
    repo.add(2)
    limited = Limited(repo, 2)
    api = _api(limited.handler)
    assert await run_backfill(api, CFG, tmp_path / "s.json", limit=25, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    await api.aclose()
    out = capsys.readouterr().out
    assert "rate limited" in out and "60" in out and "remaining: 1" in out


async def test_other_api_errors_stop_cleanly_with_state_saved(tmp_path, capsys):
    repo = FakeRepo()
    repo.add(1)
    repo.add(2)

    def failing(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues/2"):
            return httpx.Response(500, json={})
        return repo.handler(request)

    state = tmp_path / "s.json"
    api = _api(failing)
    assert await run_backfill(api, CFG, state, limit=25, dry_run=False, clock=clock, sleep=Sleeps()) == 1
    await api.aclose()
    assert _state(state)["done"] == [1] and "remaining: 1" in capsys.readouterr().out


async def test_missing_artifacts_and_announcements_are_done(tmp_path):
    repo = FakeRepo()
    repo.add(2)
    repo.issues[2]["user"] = {"login": "dependabot[bot]"}
    api = api_for(repo)
    assert await backfill(api, CFG, [1, 2], tmp_path / "s.json", clock, Sleeps()) == 2
    await api.aclose()
    assert repo.writes == []


@pytest.mark.parametrize("content", ["{broken", "[1, 2]", '{"v": 1, "done": "x"}', '{"v": 9, "done": [1]}'])
async def test_unreadable_state_starts_over(tmp_path, content):
    repo = FakeRepo()
    repo.add(1)
    state = tmp_path / "s.json"
    state.write_text(content, encoding="utf-8")
    api = api_for(repo)
    assert await backfill(api, CFG, [1], state, clock, Sleeps()) == 1
    await api.aclose()
    assert _state(state)["done"] == [1]


# --- legacy migration ---------------------------------------------------------------------------


class TimelineRepo(Repo):
    """Repo whose label timeline records who added each label (the bot account for our writes)."""

    def __init__(self) -> None:
        super().__init__()
        self.label_events: dict[int, list[tuple[str, str]]] = {}
        self.all_items: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if (m := re.fullmatch(rf"{ROOT}/issues/(\d+)/labels", path)) and request.method == "POST":
            for name in json.loads(request.content)["labels"]:
                self.label_events.setdefault(int(m[1]), []).append((name, BOT))
        if path == f"{ROOT}/issues" and request.url.params.get("state") == "all":
            page = request.url.params.get("page", "1")
            return httpx.Response(200, json=self.all_items if page == "1" else [])
        if path.endswith("/graphql") and b"issueOrPullRequest" in request.content:
            number = json.loads(request.content)["variables"]["number"]
            nodes = [
                {"label": {"name": n}, "actor": {"__typename": "User", "login": a}}
                for n, a in self.label_events.get(number, [])
            ]
            return httpx.Response(
                200, json={"data": {"repository": {"issueOrPullRequest": {"timelineItems": {"nodes": nodes}}}}}
            )
        return super().handler(request)


async def test_legacy_wip_is_reasserted_by_the_bot_and_trusted_afterwards(tmp_path):
    repo = TimelineRepo()
    repo.add(5, labels=("spec", "phase:in-progress"), body="Old spec without a checklist")  # renamed `wip`
    repo.label_events[5] = [("phase:in-progress", "someone")]
    repo.add_pr(11, body="Part of #5")
    repo.prs[11]["draft"] = True
    repo.add(8, labels=("bug", "phase:in-progress"))  # renamed `wip`, no pull request any more
    api = api_for(repo)
    assert await backfill(api, ACTIVE, [5, 8, 11], tmp_path / "s.json", clock, Sleeps()) == 3
    await api.aclose()
    # Same phase from the facts (open draft PR): the label is written again, now by the bot.
    assert ("DELETE", f"{ROOT}/issues/5/labels/phase:in-progress") in repo.writes
    assert repo.label_events[5][-1] == ("phase:in-progress", BOT)
    assert "phase:in-progress" in repo.label_names(5) and "phase:draft" in repo.label_names(11)
    # Phases come from facts only: without a PR the legacy `wip` keeps its floor (triaged).
    assert repo.label_names(8) & {"phase:in-progress", "phase:new"} == set() and "phase:triaged" in repo.label_names(8)
    # A later event trusts the bot-written label: no fall back to draft.
    await run(repo, "issues", {"action": "edited", "issue": {"number": 5}, "sender": {"login": "bob"}})
    assert "phase:in-progress" in repo.label_names(5) and "phase:draft" not in repo.label_names(5)
    assert "wait:prerequisite" not in repo.label_names(11)
    assert repo.ledger() == []


async def test_legacy_spec_with_a_merged_part_is_declared_ready(tmp_path):
    repo = TimelineRepo()
    repo.add(5, labels=("spec",), body="Old spec without a checklist")
    repo.add(6, labels=("spec",), body="Another old spec, never implemented")
    repo.add(9, labels=("spec",), body="## Definition of Ready\n- [ ] open\n")  # new style: no declaration
    repo.all_items = [
        {"number": 40, "body": "Part of #5", "pull_request": {"merged_at": "2026-09-01T00:00:00Z"}},
        {"number": 41, "body": "Closes #9", "pull_request": {"merged_at": "2026-09-01T00:00:00Z"}},
        {"number": 42, "body": "Closes #6", "pull_request": {"merged_at": None}, "state": "closed"},
        {"number": 43, "body": "Closes #6"},  # an issue, not a pull request
    ]
    api = api_for(repo)
    assert await backfill(api, ACTIVE, [5, 6, 9], tmp_path / "s.json", clock, Sleeps()) == 3
    await api.aclose()
    assert "phase:ready" in repo.label_names(5) and repo.label_events[5][-1] == ("phase:ready", BOT)
    assert "phase:draft" in repo.label_names(6) and "phase:draft" in repo.label_names(9)
    # The declaration holds in later event runs (bot-written, legacy spec without a checklist).
    repo.add_pr(12, body="Part of #5")
    await run(
        repo, "pull_request_target", {"action": "opened", "pull_request": {"number": 12}, "sender": {"login": "alice"}}
    )
    assert "wait:prerequisite" not in repo.label_names(12) and "phase:in-review" in repo.label_names(5)
    assert repo.ledger() == [] or all(e["rule"] != "V06" for e in repo.ledger())


async def test_backfill_ledger_issue_is_never_touched(tmp_path):
    repo = Repo()
    repo.add_pr(10)
    api = api_for(repo)
    await backfill(api, ACTIVE, [10, LEDGER], tmp_path / "s.json", clock, Sleeps())
    await api.aclose()
    assert not [w for w in repo.writes if f"/issues/{LEDGER}" in w[1] and "labels" not in w[1]]


# --- CLI ----------------------------------------------------------------------------------------


def test_cli_backfill(monkeypatch, tmp_path, capsys):
    repo = GraphqlRepo()
    repo.add(1)
    repo.add(2)

    def factory(token: str, name: str, **kw):
        return GitHubApi(token, name, transport=httpx.MockTransport(repo.handler), sleep=_nosleep, **kw)

    monkeypatch.setattr(main, "GitHubApi", factory)
    monkeypatch.setattr(bf, "MIN_DELAY", 0.0)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.delenv("BOT_PAT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    state = tmp_path / "s.json"
    monkeypatch.setenv("OCT_BACKFILL_STATE", str(state))
    assert main.cli(["--backfill", "--limit", "1", "--dry-run"]) == 0
    assert repo.writes == [] and "remaining: 2" in capsys.readouterr().out
    assert main.cli(["--backfill", "--limit", "1"]) == 0
    assert "remaining: 1" in capsys.readouterr().out and _state(state)["done"] == [1]
    assert main.cli(["--backfill", "--limit", "5", "--state", str(tmp_path / "other.json")]) == 0
    assert "remaining: 0" in capsys.readouterr().out
    assert main.cli(["--backfill", "--limit", "0"]) == 2


def test_rate_limit_detection():
    def resp(status: int, **headers: str) -> httpx.Response:
        return httpx.Response(status, headers=headers)

    import time

    assert bf._rate_limit(resp(403, **{"retry-after": "30"})) == 30
    reset = str(int(time.time()) + 120)
    assert 100 <= bf._rate_limit(resp(403, **{"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset})) <= 120
    assert bf._rate_limit(resp(429)) == 60
    assert bf._rate_limit(resp(403)) is None  # a permission error, not a rate limit
    assert bf._rate_limit(resp(500)) is None


async def test_listing_rate_limit_and_transport_errors(tmp_path, capsys):
    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "5"}, json={})

    api = _api(limited)
    assert await run_backfill(api, CFG, tmp_path / "s.json", limit=5, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    await api.aclose()
    assert "rate limited: retry after 5 s" in capsys.readouterr().out

    def forbidden(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Resource not accessible"})

    api = _api(forbidden)
    assert await run_backfill(api, CFG, tmp_path / "s.json", limit=5, dry_run=False, clock=clock, sleep=Sleeps()) == 1
    await api.aclose()
    assert "listing open artifacts failed" in capsys.readouterr().out

    repo = FakeRepo()
    repo.add(1)

    def broken(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues/1"):
            raise httpx.ConnectError("down")
        return repo.handler(request)

    api = _api(broken)
    assert await run_backfill(api, CFG, tmp_path / "s.json", limit=5, dry_run=False, clock=clock, sleep=Sleeps()) == 1
    await api.aclose()
    assert "ConnectError" in capsys.readouterr().out


async def test_unreadable_artifacts_are_skipped_and_stay_to_do(tmp_path, capsys):
    repo = Repo()
    repo.add(5, labels=("bug", "phase:in-progress"))
    repo.add(6, labels=("bug",))
    original = repo.handler

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/graphql") and json.loads(request.content)["variables"]["number"] == 5:
            return httpx.Response(200, json={"errors": [{"message": "boom"}]})
        if request.url.path.endswith("/issues/6/comments") and request.method == "GET":
            return httpx.Response(502, json={})
        return original(request)

    state = tmp_path / "s.json"
    api = _api(handler)
    assert await run_backfill(api, ACTIVE, state, limit=25, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    await api.aclose()
    out = capsys.readouterr().out
    assert "skipped (unreadable): 2" in out
    assert not [w for w in repo.writes if re.search(r"/issues/(5|6)(/|$)", w[1])]  # nothing written
    assert 5 not in _state(state)["done"] and 6 not in _state(state)["done"]
    api = api_for(repo)  # readable again: the next run picks them up
    assert await run_backfill(api, ACTIVE, state, limit=25, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    await api.aclose()
    out = capsys.readouterr().out
    assert "already done (state file): 1" in out and "remaining: 0" in out


async def test_long_rate_limit_stops_instead_of_sleeping(tmp_path, capsys):
    repo = FakeRepo()
    repo.add(1)
    repo.add(2)
    api_sleeps = Sleeps()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues/2"):
            return httpx.Response(403, headers={"retry-after": "3600"}, json={})
        return repo.handler(request)

    api = GitHubApi("t", "o/r", transport=httpx.MockTransport(handler), sleep=api_sleeps)
    state = tmp_path / "s.json"
    assert await run_backfill(api, CFG, state, limit=25, dry_run=False, clock=clock, sleep=Sleeps()) == 0
    await api.aclose()
    assert api_sleeps.calls == []  # never slept through the hour
    assert "retry after 3600 s" in capsys.readouterr().out and _state(state)["done"] == [1]


async def test_pull_request_phase_labels_are_never_reasserted(tmp_path):
    repo = TimelineRepo()
    repo.add_pr(11)
    repo.issues[11]["labels"].append({"name": "phase:in-review"})  # right, but not written by the bot
    api = api_for(repo)
    assert await backfill(api, ACTIVE, [11], tmp_path / "s.json", clock, Sleeps()) == 1
    await api.aclose()
    assert not [w for w in repo.writes if w[0] == "DELETE" and "phase:in-review" in w[1]]
