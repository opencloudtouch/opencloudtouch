"""Tests for the /oct commands: parsing, authorization, execution and the issue_comment pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

from oct_status import commands
from oct_status.api import GitHubApi
from oct_status.apply import MARKER
from oct_status.commands import Command, Outcome, authorize, execute, parse_command
from oct_status.main import Workspace, run_event
from oct_status.model import Derived, Phase, Review, Wait

from .conftest import FixtureTransport, make_snapshot
from .test_main_events import BOT, CFG, ROOT, FakeRepo, _nosleep, api_for

DOR_DONE = "## Definition of Ready\n- [x] one\n- [ ] two n/a here\n"
DOR_OPEN = "## Definition of Ready\n- [x] one\n- [ ] second item\n- [ ] third item\n"
# Real response shape: legacy `permission` plus the real role in `role_name` (maintain shows as write).
PERMS = {
    "alice": {"permission": "write", "role_name": "write"},
    "bob": {"permission": "write", "role_name": "write"},
    "scheilch": {"permission": "admin", "role_name": "admin"},
    "carol": {"permission": "write", "role_name": "maintain"},
    "dave": {"permission": "read", "role_name": "read"},
    "tess": {"permission": "read", "role_name": "triage"},
    "legacy": {"permission": "write"},
    "legacy-admin": {"permission": "admin"},
}


class CommandRepo(FakeRepo):
    """FakeRepo plus collaborator permissions, reactions and review requests."""

    def __init__(self) -> None:
        super().__init__()
        self.reactions: list[tuple[int, str]] = []
        self.review_requests: list[dict] = []
        self.perm_errors: set[str] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if m := re.fullmatch(rf"{ROOT}/collaborators/([^/]+)/permission", path):
            if m[1] in self.perm_errors:
                return httpx.Response(500, json={})
            if m[1] not in PERMS:
                return httpx.Response(404, json={})
            return httpx.Response(200, json=PERMS[m[1]])
        if m := re.fullmatch(rf"{ROOT}/issues/comments/(\d+)/reactions", path):
            self.writes.append((request.method, path))
            self.reactions.append((int(m[1]), json.loads(request.content)["content"]))
            return httpx.Response(201, json={})
        if re.fullmatch(rf"{ROOT}/pulls/\d+/requested_reviewers", path):
            self.writes.append((request.method, path))
            self.review_requests.append(json.loads(request.content))
            return httpx.Response(201, json={})
        return super().handler(request)

    def guide(self, number: int) -> str:
        return next((c["body"] for c in self.comments.get(number, []) if MARKER in c["body"]), "")


def comment_event(number: int, body: str, login: str = "alice", comment_id: int = 77, action: str = "created") -> dict:
    return {
        "action": action,
        "issue": {"number": number},
        "comment": {"id": comment_id, "body": body, "user": {"login": login}},
        "sender": {"login": login},
    }


def spec_repo(body: str = DOR_DONE, labels: tuple[str, ...] = ("spec",), author: str = "alice") -> CommandRepo:
    repo = CommandRepo()
    repo.add(5, body=body, labels=labels)
    repo.issues[5]["user"] = {"login": author}
    return repo


# --- parsing --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "name", "args"),
    [
        ("/oct review", "review", ""),
        ("/oct rework needs more detail", "rework", "needs more detail"),
        ("/oct ready --reviewer bob", "ready", "--reviewer bob"),
        ("/oct ready --reviewer independent-review", "ready", "--reviewer independent-review"),
        ("/oct triage", "triage", ""),
        ("/oct confirm", "confirm", ""),
        ("/oct approve", "approve", ""),
        ("/oct verified Bose SoundTouch 10", "verified", "Bose SoundTouch 10"),
        ("/oct needs-hardware-test", "needs-hardware-test", ""),
        ("/oct needs-info", "needs-info", ""),
        ("/oct designer needs a mock-up", "designer", "needs a mock-up"),
        ("/oct no-spec docs only", "no-spec", "docs only"),
        ("/oct supersede #12", "supersede", "#12"),
        ("/oct override CI is broken", "override", "CI is broken"),
        ("/oct accept-paths", "accept-paths", ""),
        ("Thanks!\n\n/OCT Review  \nmore", "review", ""),
        ("  /oct triage", "triage", ""),
    ],
)
def test_parse_all_commands(text, name, args):
    assert parse_command(text) == Command(name, args)


@pytest.mark.parametrize(
    "text",
    [
        "/octopus review",
        "/oct",
        "/oct unknown",
        "please run /oct review",
        "> /oct review",
        "```\n/oct review\n```",
        "~~~sh\n/oct review\n~~~",
        "```\n/oct review",  # unclosed fence swallows the rest
        "<!-- /oct review -->",
        "<!--\n/oct review\n-->",
        "    /oct review",
        "",
    ],
)
def test_text_that_must_not_parse(text):
    assert parse_command(text) is None


def test_command_after_a_closed_fence_parses():
    assert parse_command("```\n/oct approve\n```\n/oct triage") == Command("triage", "")


def test_nested_shorter_fence_does_not_close():
    assert parse_command("````\n```\n/oct triage\n````") is None


def test_arguments_are_stripped_and_limited():
    cmd = parse_command("/oct override " + "x" * 1000 + "\x07\x1b")
    assert cmd is not None and len(cmd.args) == commands.MAX_ARGS
    cmd = parse_command("/oct override a\x00b\x1b[31m c")
    assert cmd is not None and not any(ord(ch) < 32 for ch in cmd.args)


# --- authorization --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("login", "name", "expected"),
    [
        ("alice", "review", True),  # write
        ("dave", "review", False),  # read only
        ("tess", "review", False),  # triage role: legacy permission read
        ("tess", "triage", False),
        ("carol", "review", True),  # maintain role: legacy permission write
        ("legacy", "review", True),  # legacy shape without role_name
        ("legacy", "triage", False),
        ("legacy-admin", "triage", True),
        ("stranger", "review", False),  # not a collaborator
        ("alice", "triage", False),  # maintainer command needs maintain
        ("carol", "triage", True),
        ("scheilch", "override", True),
        ("alice", "override", False),
        ("bad login!", "review", False),  # never reaches a URL
        ("../x", "review", False),
        (BOT, "review", False),  # automation never commands
        ("github-actions[bot]", "review", False),
    ],
)
async def test_authorization(login, name, expected):
    repo = CommandRepo()
    api = api_for(repo)
    assert await authorize(api, login, Command(name, "x"), CFG) is expected
    await api.aclose()


async def test_author_permission_prefers_role_name():
    from oct_status.facts import author_permission

    repo = CommandRepo()
    api = api_for(repo)
    assert await author_permission(api, "carol") == "maintain"
    assert await author_permission(api, "legacy") == "write"
    assert await author_permission(api, "stranger") is None
    await api.aclose()


async def test_rejection_text_distinguishes_unverified_from_missing_access():
    repo = CommandRepo()
    repo.perm_errors.add("alice")
    api = api_for(repo)
    ok, reason = await commands.authorize_detailed(api, "alice", Command("review", ""), CFG)
    assert not ok and "could not be verified" in reason
    ok, reason = await commands.authorize_detailed(api, "dave", Command("review", ""), CFG)
    assert not ok and "needs write access" in reason and "verified" not in reason
    ok, reason = await commands.authorize_detailed(api, "alice", Command("triage", ""), CFG)
    assert not ok and "needs maintain access" in reason
    ok, reason = await commands.authorize_detailed(api, BOT, Command("review", ""), CFG)
    assert not ok and "automation" in reason
    await api.aclose()


@pytest.mark.parametrize("body", [b"not json", b"[1]"])
async def test_unparseable_permission_response_is_unverified(body):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    api = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep)
    ok, reason = await commands.authorize_detailed(api, "alice", Command("review", ""), CFG)
    assert not ok and "could not be verified" in reason
    await api.aclose()


async def test_authorization_fails_closed_on_api_error():
    repo = CommandRepo()
    repo.perm_errors.add("alice")
    api = api_for(repo)
    assert await authorize(api, "alice", Command("review", ""), CFG) is False
    await api.aclose()


async def test_unauthorized_command_rejected_without_writes():
    repo = spec_repo()
    api = api_for(repo)
    event = comment_event(5, "/oct review", login="dave")
    assert await run_event(api, CFG, "issue_comment", event, dry_run=False) == 0
    assert "phase:spec-review" not in repo.label_names(5)
    assert repo.reactions == [(77, "eyes"), (77, "-1")]
    assert "rejected" in repo.guide(5) and "write access" in repo.guide(5)
    assert len([c for c in repo.comments[5]]) == 1  # only the guide comment
    await api.aclose()


# --- execute: transitions -----------------------------------------------------------------------


def _derived(phase: Phase, *waits: Wait) -> Derived:
    return Derived(phase, frozenset(waits), None)


async def _run(name: str, args: str, snap, derived, actor="alice", dry_run=False, repo=None):
    api = api_for(repo or CommandRepo())
    try:
        return await execute(api, Command(name, args), snap, derived, actor, cfg=CFG, dry_run=dry_run)
    finally:
        await api.aclose()


async def test_review_by_author_declares_spec_review_and_drops_wait():
    snap = make_snapshot(body=DOR_DONE, labels=frozenset({"spec", "phase:draft", "wait:spec-fix"}), author="alice")
    out = await _run("review", "", snap, _derived(Phase.DRAFT))
    assert out.ok
    assert out.declare == {"add": ["phase:spec-review"], "remove": ["phase:draft", "wait:spec-fix"]}


async def test_review_rejected_for_other_user_incomplete_dor_and_wrong_phase():
    snap = make_snapshot(body=DOR_OPEN, labels=frozenset({"spec"}), author="alice")
    assert "author" in (await _run("review", "", snap, _derived(Phase.DRAFT), actor="bob")).message
    out = await _run("review", "", snap, _derived(Phase.DRAFT))
    assert not out.ok and "second item" in out.message and "third item" in out.message
    done = make_snapshot(body=DOR_DONE, labels=frozenset({"spec"}), author="alice")
    out = await _run("review", "", done, _derived(Phase.READY))
    assert not out.ok and "not valid" in out.message


async def test_commands_on_the_wrong_kind_are_rejected():
    bug = make_snapshot(labels=frozenset({"bug"}))
    assert "only applies to a spec" in (await _run("rework", "why", bug, _derived(Phase.NEW))).message


async def test_rework_sets_wait_and_needs_reason():
    snap = make_snapshot(body=DOR_DONE, labels=frozenset({"spec", "phase:spec-review"}), author="alice")
    assert not (await _run("rework", "", snap, _derived(Phase.SPEC_REVIEW), actor="bob")).ok
    out = await _run("rework", "unclear scope", snap, _derived(Phase.SPEC_REVIEW), actor="bob")
    assert out.ok
    assert out.declare == {"add": ["phase:spec-rework", "wait:spec-fix"], "remove": ["phase:spec-review"]}


async def test_ready_requires_complete_dor_and_other_reviewer():
    labels = frozenset({"spec", "phase:spec-review"})
    snap = make_snapshot(body=DOR_DONE, labels=labels, author="scheilch")
    derived = _derived(Phase.SPEC_REVIEW)
    # the author may not name himself, nor declare readiness without the independent review
    assert "differ" in (await _run("ready", "--reviewer scheilch", snap, derived, actor="scheilch")).message
    assert "independent-review" in (await _run("ready", "--reviewer bob", snap, derived, actor="scheilch")).message
    ok = await _run("ready", "--reviewer independent-review", snap, derived, actor="scheilch")
    assert ok.ok and ok.declare["add"] == ["phase:ready"]
    # a second person names himself
    ok = await _run("ready", "--reviewer bob", snap, derived, actor="bob")
    assert ok.ok and "bob" in ok.message
    # reviewer argument missing or malformed
    for args in ("", "bob", "--reviewer", "--reviewer a/b", "--reviewer bob extra"):
        assert not (await _run("ready", args, snap, derived, actor="bob")).ok
    # unticked items are listed
    open_snap = make_snapshot(body=DOR_OPEN, labels=labels, author="scheilch")
    out = await _run("ready", "--reviewer bob", open_snap, derived, actor="bob")
    assert not out.ok and "second item; third item" in out.message


async def test_triage_confirm_follow_the_state_machine():
    bug = make_snapshot(labels=frozenset({"bug"}))
    out = await _run("triage", "", bug, _derived(Phase.NEW), actor="carol")
    assert out.ok and out.declare == {"add": ["phase:triaged"], "remove": []}
    assert not (await _run("confirm", "", bug, _derived(Phase.NEW), actor="carol")).ok
    triaged = make_snapshot(labels=frozenset({"bug", "phase:triaged"}))
    out = await _run("confirm", "", triaged, _derived(Phase.TRIAGED), actor="carol")
    assert out.ok and out.declare == {"add": ["phase:confirmed"], "remove": ["phase:triaged"]}


async def test_announcement_has_no_workflow():
    out = await _run("triage", "", make_snapshot(), None)
    assert not out.ok


# --- execute: waits, approve, no-spec, supersede, override -------------------------------------------


async def test_waits_and_verified():
    snap = make_snapshot(labels=frozenset({"bug", "phase:triaged", "wait:hardware-test"}))
    derived = _derived(Phase.TRIAGED, Wait.HARDWARE_TEST)
    out = await _run("verified", "Bose 10", snap, derived, actor="carol")
    assert out.ok and out.declare == {"add": [], "remove": ["wait:hardware-test"]}
    assert not (await _run("verified", "", snap, derived, actor="carol")).ok
    assert (await _run("needs-hardware-test", "", snap, derived)).declare["add"] == []  # already set
    plain = make_snapshot(labels=frozenset({"bug", "phase:triaged"}))
    assert (await _run("needs-hardware-test", "", plain, derived)).declare == {
        "add": ["wait:hardware-test"],
        "remove": [],
    }
    assert (await _run("needs-info", "", plain, derived)).declare["add"] == ["wait:reporter"]
    assert not (await _run("designer", "", plain, derived)).ok
    assert (await _run("designer", "icons", plain, derived)).declare["add"] == ["wait:designer"]


async def test_no_spec_requires_reason_and_pr_author():
    pr = make_snapshot(is_pr=True, author="alice", title="feat: x")
    derived = _derived(Phase.IN_REVIEW)
    assert not (await _run("no-spec", "", pr, derived)).ok
    assert "author" in (await _run("no-spec", "ok", pr, derived, actor="bob")).message
    assert "pull request" in (await _run("no-spec", "ok", make_snapshot(author="alice"), derived)).message
    out = await _run("no-spec", "typo fix", pr, derived)
    assert out.ok and out.no_spec_reason == "typo fix" and out.declare == {}


async def test_supersede_needs_closed_artifact_and_other_number():
    closed = make_snapshot(state="closed", labels=frozenset({"bug"}), number=5)
    derived = _derived(Phase.CLOSED)
    out = await _run("supersede", "#9", closed, derived, actor="carol")
    assert out.ok and out.declare == {"add": ["resolution:superseded"], "remove": []}
    for args in ("", "9", "#5", "#9 and more"):
        assert not (await _run("supersede", args, closed, derived)).ok
    opened = make_snapshot(labels=frozenset({"bug"}), number=5)
    assert "Close" in (await _run("supersede", "#9", opened, _derived(Phase.NEW))).message


async def test_override_and_accept_paths_are_logged():
    snap = make_snapshot(is_pr=True)
    out = await _run("override", "flaky", snap, _derived(Phase.IN_REVIEW), actor="scheilch")
    assert out.ok and out.log == "override by scheilch: flaky"
    assert "guide only" in out.message and "no effect yet" in out.message
    assert not (await _run("override", "", snap, _derived(Phase.IN_REVIEW))).ok
    out = await _run("accept-paths", "", snap, _derived(Phase.IN_REVIEW), actor="scheilch")
    assert out.ok and out.log == "accept-paths by scheilch"
    assert "guide only" in out.message and "no effect yet" in out.message


async def test_approve_requests_oct_support_review():
    repo = CommandRepo()
    pr = make_snapshot(number=8, is_pr=True, author="alice")
    out = await _run("approve", "", pr, _derived(Phase.IN_REVIEW), repo=repo)
    assert out.ok
    assert repo.review_requests == [{"reviewers": ["oct-support"]}]
    # an earlier review of an older head does not matter: the same call re-requests the review
    reviews = (Review("oct-support", "APPROVED", "old-head"),)
    old = make_snapshot(number=8, is_pr=True, author="alice", head_sha="new-head", reviews=reviews)
    assert (await _run("approve", "", old, _derived(Phase.IN_REVIEW, Wait.MAINTAINER), repo=repo)).ok
    assert repo.review_requests == [{"reviewers": ["oct-support"]}] * 2


async def test_approve_restrictions_and_dry_run():
    repo = CommandRepo()
    pr = make_snapshot(number=8, is_pr=True, author="alice")
    derived = _derived(Phase.IN_REVIEW)
    assert not (await _run("approve", "", pr, derived, actor="bob", repo=repo)).ok  # neither author nor maintainer
    assert (await _run("approve", "", pr, derived, actor="carol", repo=repo)).ok  # maintainer
    repo.perm_errors.add("bob")
    assert not (await _run("approve", "", pr, derived, actor="bob", repo=repo)).ok  # API error fails closed
    assert not (await _run("approve", "", make_snapshot(), derived, repo=repo)).ok  # issue
    assert not (await _run("approve", "", make_snapshot(is_pr=True, merged=True), derived, repo=repo)).ok
    before = len(repo.review_requests)
    out = await _run("approve", "", pr, derived, dry_run=True, repo=repo)
    assert out.ok and "would" in out.message and len(repo.review_requests) == before


async def test_approve_reports_a_refused_request():
    transport = FixtureTransport(extra={f"POST {ROOT}/pulls/8/requested_reviewers": (422, {"message": "no"})})
    api = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep)
    pr = make_snapshot(number=8, is_pr=True, author="alice")
    out = await execute(api, Command("approve", ""), pr, _derived(Phase.IN_REVIEW), "alice", cfg=CFG)
    assert not out.ok and "422" in out.message
    await api.aclose()


# --- helpers ------------------------------------------------------------------------------------------


async def test_react_and_declaration_helpers():
    transport = FixtureTransport(
        extra={
            f"POST {ROOT}/issues/comments/1/reactions": (201, {}),
            f"POST {ROOT}/issues/comments/2/reactions": (403, {}),
            f"POST {ROOT}/issues/3/labels": [],
            f"DELETE {ROOT}/issues/3/labels/wait%3Aci": (404, {}),
        }
    )
    api = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep)
    assert await commands.react(api, 1, "+1", dry_run=False)
    assert not await commands.react(api, 2, "+1", dry_run=False)
    assert not await commands.react(api, 1, "+1", dry_run=True)
    done = await commands.apply_declaration(api, 3, {"add": ["a"], "remove": ["wait:ci"]}, dry_run=False)
    assert done == ["add labels a", "remove label wait:ci"]
    ro = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep, read_only=True)
    assert await commands.apply_declaration(ro, 3, {"add": ["a"], "remove": ["b"]}, dry_run=True) == [
        "add labels a",
        "remove label b",
    ]
    await ro.aclose()
    await api.aclose()


async def test_react_swallows_transport_errors():
    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    api = GitHubApi("t", "o/r", transport=httpx.MockTransport(boom), sleep=_nosleep)
    assert not await commands.react(api, 1, "eyes", dry_run=False)
    await api.aclose()


async def test_find_no_spec_only_counts_the_pr_author_with_write_access():
    comments = [
        {"id": 1, "user": {"login": "bob"}, "body": "/oct no-spec not mine"},
        {"id": 2, "user": {"login": "alice"}, "body": "```\n/oct no-spec quoted\n```"},
        {"id": 3, "user": {"login": "alice"}, "body": "/oct no-spec first"},
        {"id": 4, "user": {"login": "alice"}, "body": "/oct no-spec latest"},
        {"id": 5, "user": None, "body": "/oct no-spec ghost"},
    ]
    transport = FixtureTransport(extra={f"GET {ROOT}/issues/9/comments": lambda r: comments})
    api = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep)
    pr = make_snapshot(number=9, is_pr=True, author="alice", author_permission="write")
    assert await commands.find_no_spec(api, pr) == "latest"
    assert await commands.find_no_spec(api, make_snapshot(number=9, is_pr=True, author="alice")) is None
    assert await commands.find_no_spec(api, make_snapshot(number=9, author="alice", author_permission="write")) is None
    await api.aclose()


# --- the pipeline -------------------------------------------------------------------------------------


async def test_issue_comment_event_executes_command_and_updates_guide():
    repo = spec_repo()
    api = api_for(repo)
    event = comment_event(5, "Looks good.\n/oct review")
    assert await run_event(api, CFG, "issue_comment", event, dry_run=False) == 0
    assert repo.label_names(5) >= {"spec", "phase:spec-review"}
    assert repo.reactions == [(77, "eyes"), (77, "+1")]
    guide = repo.guide(5)
    assert "/oct review by alice" in guide and "spec is now spec-review" in guide
    assert len(repo.comments[5]) == 1
    await api.aclose()


async def test_rejection_goes_into_the_single_guide_comment():
    repo = spec_repo(body=DOR_OPEN)
    api = api_for(repo)
    assert await run_event(api, CFG, "issue_comment", comment_event(5, "/oct review"), dry_run=False) == 0
    assert "phase:spec-review" not in repo.label_names(5)
    assert repo.reactions == [(77, "eyes"), (77, "-1")]
    guide = repo.guide(5)
    assert "was rejected" in guide and "second item" in guide
    assert len(repo.comments[5]) == 1
    await api.aclose()


async def test_dry_run_never_writes_and_reports_the_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = spec_repo()
    transport = httpx.MockTransport(repo.handler)
    api = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep, read_only=True)
    assert await run_event(api, CFG, "issue_comment", comment_event(5, "/oct review"), dry_run=True) == 0
    assert repo.writes == [] and repo.reactions == []
    text = summary.read_text()
    assert "accepted" in text and "add labels phase:spec-review" in text and "dry-run, planned" in text
    await api.aclose()


async def test_dry_run_approve_does_not_call_the_api():
    repo = CommandRepo()
    repo.add(8)
    repo.issues[8]["user"] = {"login": "alice"}
    transport = httpx.MockTransport(repo.handler)
    api = GitHubApi("t", "o/r", transport=transport, sleep=_nosleep, read_only=True)
    assert await run_event(api, CFG, "issue_comment", comment_event(8, "/oct approve"), dry_run=True) == 0
    assert repo.writes == [] and repo.review_requests == []
    await api.aclose()


@pytest.mark.parametrize(
    "event",
    [
        comment_event(5, "/oct review", action="edited"),
        comment_event(5, "no command here"),
        comment_event(5, "/octopus review"),
        comment_event(5, "/oct review", login="bad login"),
        {"action": "created", "issue": {"number": 5}, "comment": {"body": 5}, "sender": {"login": "alice"}},
        {"action": "created", "issue": {"number": 5}, "sender": {"login": "alice"}},
    ],
)
async def test_comments_without_a_command_change_nothing(event):
    repo = spec_repo()
    api = api_for(repo)
    assert await run_event(api, CFG, "issue_comment", event, dry_run=False) == 0
    assert "phase:spec-review" not in repo.label_names(5)
    assert repo.reactions == []
    await api.aclose()


async def test_command_on_a_missing_artifact_is_skipped():
    repo = CommandRepo()
    api = api_for(repo)
    assert await run_event(api, CFG, "issue_comment", comment_event(404, "/oct review"), dry_run=False) == 0
    assert repo.writes == []
    await api.aclose()


async def test_command_without_comment_id_still_runs():
    repo = spec_repo()
    api = api_for(repo)
    event = comment_event(5, "/oct review")
    del event["comment"]["id"]
    assert await run_event(api, CFG, "issue_comment", event, dry_run=False) == 0
    assert "phase:spec-review" in repo.label_names(5) and repo.reactions == []
    await api.aclose()


async def test_http_failure_while_executing_is_a_rejection(monkeypatch: pytest.MonkeyPatch):
    async def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(commands, "execute", boom)
    repo = spec_repo()
    api = api_for(repo)
    assert await run_event(api, CFG, "issue_comment", comment_event(5, "/oct review"), dry_run=False) == 0
    assert "phase:spec-review" not in repo.label_names(5)
    assert repo.reactions == [(77, "eyes"), (77, "-1")]
    assert "ConnectError" in repo.guide(5)
    await api.aclose()


async def test_no_spec_comment_waives_the_spec_requirement_in_later_runs():
    pr = make_snapshot(number=9, is_pr=True, author="alice", author_permission="write", title="feat: x")
    from oct_status.model import Kind
    from oct_status.rules import detect_kind

    assert detect_kind(pr, CFG) == Kind.PULL_REQUEST
    waived = make_snapshot(number=9, is_pr=True, author="alice", title="feat: x", no_spec_reason="why")
    assert detect_kind(waived, CFG) == Kind.DOCS_PR


FIX_REPO = "opencloudtouch/opencloudtouch"
FIX_ROOT = f"/repos/{FIX_REPO}"


def _fixture_api(extra: dict) -> GitHubApi:
    routes = {f"GET {FIX_ROOT}/pulls": [], f"GET {FIX_ROOT}/collaborators/scheilch/permission": {"permission": "admin"}}
    transport = FixtureTransport(numbers=[574], extra={**routes, **extra})
    return GitHubApi("t", FIX_REPO, transport=transport, sleep=_nosleep)


async def test_workspace_load_reads_the_no_spec_waiver():
    comments = [{"id": 1, "user": {"login": "scheilch"}, "body": "/oct no-spec tooling only"}]
    api = _fixture_api({f"GET {FIX_ROOT}/issues/574/comments": lambda r: comments})
    snap = await Workspace(api, CFG).load(574)
    assert snap is not None and snap.no_spec_reason == "tooling only"
    await api.aclose()


async def test_workspace_load_survives_unreadable_comments():
    api = _fixture_api({f"GET {FIX_ROOT}/issues/574/comments": (500, {})})
    ws = Workspace(api, CFG)
    snap = await ws.load(574)
    assert snap is not None and snap.no_spec_reason is None
    assert any("unreadable" in w for w in ws.warnings)
    await api.aclose()


def test_outcome_defaults():
    out = Outcome(True, "x")
    assert out.declare == {} and out.effects == [] and out.log is None


async def test_label_write_failure_is_a_rejection_with_notice():
    repo = spec_repo()
    original = repo.handler
    failed: list[int] = []

    def failing(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/issues/5/labels") and len(failed) < 4:
            failed.append(1)  # the declaration fails through all retries; later convergence works
            return httpx.Response(500, json={})
        return original(request)

    api = GitHubApi("t", "o/r", transport=httpx.MockTransport(failing), sleep=_nosleep)
    assert await run_event(api, CFG, "issue_comment", comment_event(5, "/oct review"), dry_run=False) == 0
    assert repo.reactions == [(77, "eyes"), (77, "-1")]
    assert "was rejected" in repo.guide(5) and "HTTPStatusError" in repo.guide(5)
    await api.aclose()


async def test_unverifiable_permission_is_reported_in_the_guide():
    repo = spec_repo()
    repo.perm_errors.add("bob")
    api = api_for(repo)
    event = comment_event(5, "/oct review", login="bob")
    assert await run_event(api, CFG, "issue_comment", event, dry_run=False) == 0
    assert "could not be verified" in repo.guide(5)
    assert "phase:spec-review" not in repo.label_names(5)
    await api.aclose()


async def test_maintain_role_passes_triage_and_override_is_labelled_not_effective():
    repo = CommandRepo()
    repo.add(6, labels=("bug",))
    api = api_for(repo)
    assert (
        await run_event(api, CFG, "issue_comment", comment_event(6, "/oct triage", login="carol"), dry_run=False) == 0
    )
    assert "phase:triaged" in repo.label_names(6)
    await run_event(api, CFG, "issue_comment", comment_event(6, "/oct override why", login="carol"), dry_run=False)
    assert "no effect yet" in repo.guide(6)
    await api.aclose()
