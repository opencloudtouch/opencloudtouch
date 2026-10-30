"""Tests for the idempotent applier against an in-memory fake GitHub."""

from __future__ import annotations

import json
from urllib.parse import unquote

import httpx

from oct_status.api import GitHubApi
from oct_status.apply import MARKER, apply_state, guides_in, is_own_event, upsert_guide
from oct_status.config import Actor, Config
from oct_status.model import Derived, Graph, Phase, Resolution, Wait
from oct_status.render import render_block
from oct_status.render import splice_block as render_splice

from .conftest import make_snapshot

REPO = "o/r"
ROOT = f"/repos/{REPO}"
BOT = "oct-support"
CFG = Config(
    automation={
        BOT: Actor(BOT, "automation"),
        "dependabot[bot]": Actor("dependabot[bot]", "automation", block_location="comment"),
    },
    gate_checks=[],
    protected_paths=[],
    bot_logins=(BOT, "github-actions[bot]"),
)
GUIDE = f"{MARKER}\n\nguide v1\n"


class FakeGitHub:
    def __init__(self, labels: set[str] | None = None, body: str = "") -> None:
        self.labels = set(labels or ())
        self.body = body
        self.comments: list[dict] = []
        self.writes: list[tuple[str, str]] = []
        self._next = 100
        self.reads = 0  # GET of the issue itself (the re-read before a description write)
        self.on_read = None  # hook: simulate an edit that lands between our read and our write

    def add_comment(self, text: str, login: str = BOT) -> int:
        self._next += 1
        self.comments.append({"id": self._next, "body": text, "user": {"login": login}})
        return self._next

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        method = request.method
        body = json.loads(request.content) if request.content else {}
        if method != "GET":
            self.writes.append((method, path))
        if path == f"{ROOT}/issues/1/comments" and method == "GET":
            page = int(request.url.params.get("page", "1"))
            return httpx.Response(200, json=self.comments if page == 1 else [])
        if path == f"{ROOT}/issues/1/comments" and method == "POST":
            return httpx.Response(201, json={"id": self.add_comment(body["body"])})
        if path.startswith(f"{ROOT}/issues/comments/"):
            cid = int(path.rsplit("/", 1)[1])
            found = next((c for c in self.comments if c["id"] == cid), None)
            if found is None:
                return httpx.Response(404, json={})
            if method == "PATCH":
                found["body"] = body["body"]
                return httpx.Response(200, json=found)
            if method == "DELETE":
                self.comments.remove(found)
                return httpx.Response(204)
        if path == f"{ROOT}/issues/1/labels" and method == "POST":
            self.labels |= set(body["labels"])
            return httpx.Response(200, json=[])
        if path.startswith(f"{ROOT}/issues/1/labels/") and method == "DELETE":
            self.labels.discard(path[len(f"{ROOT}/issues/1/labels/") :])
            return httpx.Response(200, json=[])
        if path == f"{ROOT}/issues/1" and method == "GET":
            self.reads += 1
            if self.on_read is not None:
                self.on_read(self)
            return httpx.Response(200, json={"number": 1, "body": self.body})
        if path == f"{ROOT}/issues/1" and method == "PATCH":
            self.body = body["body"]
            return httpx.Response(200, json={})
        return httpx.Response(404, json={})


def make(fake: FakeGitHub) -> GitHubApi:
    return GitHubApi("t", REPO, transport=httpx.MockTransport(fake.handler), sleep=_nosleep)


async def _nosleep(_: float) -> None:
    return None


DERIVED = Derived(Phase.IN_REVIEW, frozenset({Wait.CI}), None)


def snap_of(fake: FakeGitHub, **kw):
    return make_snapshot(labels=frozenset(fake.labels), body=fake.body, is_pr=True, **kw)


def block_for(snap, derived=DERIVED):
    return render_block(snap, derived, Graph([], {snap.number: snap}, {}), CFG)


async def converge(fake, derived=DERIVED, guide=GUIDE, **kw):
    api = make(fake)
    snap = snap_of(fake, **kw)
    out = await apply_state(api, snap, derived, block_for(snap, derived), guide, CFG)
    await api.aclose()
    return out


async def test_second_run_makes_zero_writes():
    fake = FakeGitHub(labels={"bug"}, body="Hello")
    first = await converge(fake)
    assert first
    writes = len(fake.writes)
    assert await converge(fake) == []
    assert len(fake.writes) == writes


async def test_only_owned_namespaces_change():
    fake = FakeGitHub(labels={"bug", "phase:ready", "wait:maintainer", "resolution:wontfix", "type:x"})
    await converge(fake)
    assert fake.labels == {"bug", "type:x", "phase:in-review", "wait:ci"}


async def test_resolution_label_added():
    fake = FakeGitHub()
    await converge(fake, derived=Derived(Phase.CLOSED, frozenset(), Resolution.DUPLICATE))
    assert fake.labels == {"phase:closed", "resolution:duplicate"}


async def test_dependency_pr_uses_pinned_comment():
    fake = FakeGitHub(body="dependabot body")
    out = await converge(fake, author="dependabot[bot]")
    assert fake.body == "dependabot body"
    assert not any(path.endswith("/issues/1") for _, path in fake.writes)
    assert len(fake.comments) == 1
    text = fake.comments[0]["body"]
    assert text.startswith(f"{MARKER}\n<!-- oct-status:v1")
    assert out
    fake.body = "regenerated by dependabot"  # dependabot rewrites its body
    assert await converge(fake, author="dependabot[bot]") == []
    assert fake.body == "regenerated by dependabot"


async def test_guide_upsert_updates_in_place():
    fake = FakeGitHub()
    api = make(fake)
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "created"
    assert [m for m, _ in fake.writes] == ["POST"]
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "unchanged"
    assert len(fake.writes) == 1
    assert await upsert_guide(api, 1, GUIDE + "more", CFG.bot_logins) == "updated"
    assert fake.writes[-1][0] == "PATCH" and len(fake.comments) == 1
    await api.aclose()


async def test_guide_ignores_marker_from_foreign_author():
    fake = FakeGitHub()
    fake.add_comment(GUIDE, login="mallory")
    api = make(fake)
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "created"
    assert len(fake.comments) == 2
    await api.aclose()


async def test_guide_found_on_second_page():
    fake = FakeGitHub()
    for n in range(100):
        fake.add_comment(f"chatter {n}", login="human")
    fake.add_comment(GUIDE)
    orig = fake.handler

    def paged(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/comments"):
            page, size = int(request.url.params["page"]), int(request.url.params["per_page"])
            return httpx.Response(200, json=fake.comments[(page - 1) * size : page * size])
        return orig(request)

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(paged), sleep=_nosleep)
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "unchanged"
    assert fake.writes == []
    await api.aclose()


def test_guides_in_ignores_marker_from_non_bot_author():
    comments = [
        {"id": 1, "body": GUIDE, "user": {"login": "mallory"}},
        {"id": 2, "body": GUIDE, "user": None},
        {"id": 3, "body": GUIDE, "user": {"login": BOT}},
    ]
    assert [c["id"] for c in guides_in(comments, CFG.bot_logins)] == [3]


async def test_duplicate_guides_keep_oldest():
    fake = FakeGitHub()
    oldest = fake.add_comment(GUIDE)
    fake.add_comment(GUIDE)
    fake.add_comment(GUIDE)
    api = make(fake)
    assert await upsert_guide(api, 1, GUIDE + "new", CFG.bot_logins) == "deduplicated"
    assert [c["id"] for c in fake.comments] == [oldest]
    assert fake.comments[0]["body"] == GUIDE + "new"
    assert [m for m, _ in fake.writes] == ["DELETE", "DELETE", "PATCH"]
    await api.aclose()


async def test_deleted_guide_is_recreated():
    fake = FakeGitHub()
    api = make(fake)
    await upsert_guide(api, 1, GUIDE, CFG.bot_logins)
    fake.comments.clear()
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "created"
    assert len(fake.comments) == 1
    await api.aclose()


async def test_dry_run_writes_nothing_and_reports_plan():
    fake = FakeGitHub(labels={"phase:ready"}, body="Hello")
    api = make(fake)
    snap = snap_of(fake)
    plan = await apply_state(api, snap, DERIVED, block_for(snap), GUIDE, CFG, dry_run=True)
    await api.aclose()
    assert fake.writes == []
    assert any("phase:in-review" in p for p in plan) and any("body" in p for p in plan)
    assert any("guide" in p for p in plan)


async def test_announcement_gets_neither_block_nor_guide():
    fake = FakeGitHub(labels={"phase:ready"})
    api = make(fake)
    out = await apply_state(api, snap_of(fake), DERIVED, None, None, CFG)
    await api.aclose()
    assert out == [] and fake.writes == []


async def test_truncated_body_is_not_rewritten_every_run(monkeypatch):
    rows = "\n".join(f"| #{n} | implements | open | x |" for n in range(2, 12))
    block = f"<!-- oct-status:v1 hash=0123456789ab -->\nhead\n\n| a | b | c | d |\n|---|---|---|---|\n{rows}\n<!-- /oct-status -->"
    import oct_status.apply as apply_mod

    real = apply_mod.splice_block
    monkeypatch.setattr(apply_mod, "splice_block", lambda body, blk: real(body, blk, limit=len(blk) - 100))
    fake = FakeGitHub(body="text")
    for expected in (1, 0):  # shortened block is written once, then stable
        api = make(fake)
        out = await apply_state(api, snap_of(fake), DERIVED, block, None, CFG)
        await api.aclose()
        assert sum("body" in o for o in out) == expected
    assert fake.body != real("text", block) and "more" in fake.body


def test_bot_edit_event_is_ignored():
    payload = {"action": "edited", "sender": {"login": BOT}}
    assert is_own_event("issues", payload, {BOT})
    assert is_own_event("pull_request", {"action": "edited", "sender": {"login": BOT}}, {BOT})
    assert not is_own_event("issues", {"action": "edited", "sender": {"login": "human"}}, {BOT})
    assert not is_own_event("issues", {"action": "edited"}, {BOT})


def test_own_event_matrix():
    bot = {"login": BOT}
    assert not is_own_event("pull_request_review", {"action": "submitted", "sender": bot}, {BOT})
    assert not is_own_event("pull_request_review_comment", {"action": "created", "sender": bot}, {BOT})
    assert not is_own_event("check_suite", {"action": "completed", "sender": bot}, {BOT})
    assert is_own_event("pull_request_target", {"action": "labeled", "sender": bot}, {BOT})
    assert is_own_event("issues", {"action": "unlabeled", "sender": bot}, {BOT})
    assert not is_own_event("issues", {"action": "labeled", "sender": {"login": "human"}}, {BOT})
    assert not is_own_event("issues", {"action": "opened", "sender": bot}, {BOT})
    assert is_own_event("issues", {"action": "reopened", "sender": bot}, {BOT})  # V08 revert reopens the issue
    assert not is_own_event("issues", {"action": "reopened", "sender": {"login": "human"}}, {BOT})
    assert not is_own_event("pull_request", {"action": "reopened", "sender": bot}, {BOT})
    guide = {"action": "created", "sender": bot, "comment": {"body": GUIDE}}
    assert is_own_event("issue_comment", guide, {BOT})
    answer = {"action": "created", "sender": bot, "comment": {"body": "Thanks, see docs"}}
    assert not is_own_event("issue_comment", answer, {BOT})
    human = {"action": "created", "sender": {"login": "h"}, "comment": {"body": GUIDE}}
    assert not is_own_event("issue_comment", human, {BOT})


async def test_dependency_pr_without_guide_is_stable():
    fake = FakeGitHub(body="dependabot body")
    assert await converge(fake, author="dependabot[bot]", guide=None)
    assert len(fake.comments) == 1 and fake.comments[0]["body"].startswith(MARKER)
    writes = len(fake.writes)
    assert await converge(fake, author="dependabot[bot]", guide=None) == []
    assert len(fake.writes) == writes and len(fake.comments) == 1


async def test_dependency_pr_with_guide_is_stable_and_marker_once():
    fake = FakeGitHub()
    await converge(fake, author="dependabot[bot]")
    assert fake.comments[0]["body"].count(MARKER) == 1
    assert await converge(fake, author="dependabot[bot]") == []
    assert len(fake.comments) == 1


async def test_guide_author_must_be_our_bot():
    fake = FakeGitHub()
    gitar = fake.add_comment(GUIDE, login="gitar-bot[bot]")
    human = fake.add_comment(GUIDE, login="human")
    api = make(fake)
    assert await upsert_guide(api, 1, GUIDE + "x", CFG.bot_logins) == "created"
    assert {c["id"] for c in fake.comments if c["id"] in (gitar, human)} == {gitar, human}
    assert all(c["body"] == GUIDE for c in fake.comments if c["id"] in (gitar, human))
    assert [m for m, _ in fake.writes] == ["POST"]
    fake.comments.pop()
    fake.add_comment(GUIDE, login="github-actions[bot]")
    assert await upsert_guide(api, 1, GUIDE + "x", CFG.bot_logins) == "updated"
    await api.aclose()


async def test_guide_found_on_second_comments_page():
    fake = FakeGitHub()
    filler = [{"id": i, "body": "chatter", "user": {"login": "human"}} for i in range(1, 101)]
    guide = {"id": 500, "body": GUIDE, "user": {"login": "github-actions[bot]"}}
    pages = {"1": filler, "2": [guide]}
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == f"{ROOT}/issues/1/comments":
            page = request.url.params.get("page", "1")
            seen.append(page)
            return httpx.Response(200, json=pages.get(page, []))
        fake.writes.append((request.method, request.url.path))
        return httpx.Response(200, json={})

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(handler), sleep=_nosleep)
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "unchanged"
    assert await upsert_guide(api, 1, GUIDE + "x", CFG.bot_logins) == "updated"
    await api.aclose()
    assert seen[:2] == ["1", "2"]
    assert fake.writes == [("PATCH", f"{ROOT}/issues/comments/500")]


async def test_guide_without_marker_gets_exactly_one():
    fake = FakeGitHub()
    api = make(fake)
    assert await upsert_guide(api, 1, "plain text", CFG.bot_logins) == "created"
    assert fake.comments[0]["body"] == f"{MARKER}\nplain text"
    assert await upsert_guide(api, 1, "plain text", CFG.bot_logins) == "unchanged"
    assert fake.comments[0]["body"].count(MARKER) == 1
    await api.aclose()


async def test_label_names_are_compared_case_insensitively():
    """GitHub treats label names case-insensitively: a differently spelled label is not churned."""
    fake = FakeGitHub(labels={"Phase:In-Review", "WAIT:CI", "Wait:Maintainer"})
    out = await converge(fake)
    assert not any("add labels" in o for o in out)
    assert [o for o in out if "remove label" in o] == ["remove label Wait:Maintainer"]
    assert fake.labels == {"Phase:In-Review", "WAIT:CI"}
    assert not any(m == "POST" and p.endswith("/labels") for m, p in fake.writes)


async def test_label_removal_answered_404_is_tolerated():
    """The label was removed by someone else meanwhile: the goal is reached, the run continues."""
    fake = FakeGitHub(labels={"phase:ready"}, body="Hello")
    orig = fake.handler

    def gone(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE" and "/labels/" in request.url.path:
            fake.writes.append(("DELETE", request.url.path))
            return httpx.Response(404, json={"message": "Label does not exist"})
        return orig(request)

    api = GitHubApi("t", REPO, transport=httpx.MockTransport(gone), sleep=_nosleep)
    snap = snap_of(fake)
    out = await apply_state(api, snap, DERIVED, block_for(snap), GUIDE, CFG)
    await api.aclose()
    assert "remove label phase:ready" in out
    assert "update status block in body" in out and fake.comments  # later writes still happen


async def test_human_edit_between_read_and_write_survives():
    """Lost update: the description is re-read right before the PATCH and the block spliced into it."""
    fake = FakeGitHub(body="Hello")
    api = make(fake)
    snap = snap_of(fake)  # what the run read
    fake.body = "Hello, with an edit made while the run was computing"
    rendered: list[str] = []

    def rerender(body: str) -> str:
        rendered.append(body)
        return block_for(snap_of(fake))

    warnings: list[str] = []
    out = await apply_state(api, snap, DERIVED, block_for(snap), None, CFG, rerender=rerender, warnings=warnings)
    await api.aclose()
    assert "update status block in body" in out and warnings == []
    assert fake.body.endswith("Hello, with an edit made while the run was computing")
    assert fake.body.startswith("<!-- oct-status:v1")
    assert rendered == ["Hello, with an edit made while the run was computing"]


async def test_unchanged_description_is_re_read_once_and_written():
    fake = FakeGitHub(body="Hello")
    api = make(fake)
    snap = snap_of(fake)
    out = await apply_state(api, snap, DERIVED, block_for(snap), None, CFG)
    await api.aclose()
    assert "update status block in body" in out and fake.reads == 1 and fake.body.endswith("Hello")


async def test_description_that_keeps_changing_is_skipped_with_a_warning():
    fake = FakeGitHub(body="Hello")
    api = make(fake)
    snap = snap_of(fake)

    def edit(f: FakeGitHub) -> None:
        f.body += " more"  # every read sees another edit

    fake.on_read = edit
    warnings: list[str] = []
    out = await apply_state(api, snap, DERIVED, block_for(snap), None, CFG, warnings=warnings)
    await api.aclose()
    assert "update status block in body" not in out
    assert not any(m == "PATCH" for m, _ in fake.writes) and "oct-status:v1" not in fake.body
    assert warnings == ["WARNING: description of #1 changed during this run; status block not rewritten"]


async def test_fresh_description_that_already_carries_the_block_is_not_written():
    fake = FakeGitHub(body="Hello")
    api = make(fake)
    snap = snap_of(fake)
    block = block_for(snap)
    fake.body = render_splice(fake.body, block)  # an overlapping run already wrote it
    out = await apply_state(api, snap, DERIVED, block, None, CFG)
    await api.aclose()
    assert out == ["add labels phase:in-review, wait:ci"] and not any(m == "PATCH" for m, _ in fake.writes)


async def test_dry_run_does_not_re_read_the_description():
    fake = FakeGitHub(body="Hello")
    api = make(fake)
    snap = snap_of(fake)
    out = await apply_state(api, snap, DERIVED, block_for(snap), None, CFG, dry_run=True)
    await api.aclose()
    assert "update status block in body" in out and fake.reads == 0


def test_guides_in_adopts_only_a_bot_comment_that_starts_with_the_marker():
    """A bot comment that merely quotes the marker (an issue-handler answer) is never adopted."""
    comments = [
        {"id": 1, "body": f"Answer quoting {MARKER} in the middle", "user": {"login": BOT}},
        {"id": 2, "body": f"> {MARKER}\nquoted", "user": {"login": BOT}},
        {"id": 3, "body": f"﻿ \n\t{MARKER}\nguide", "user": {"login": BOT}},  # BOM and whitespace allowed
        {"id": 4, "body": f"{MARKER}\nguide", "user": {"login": "mallory"}},
        {"id": 5, "body": None, "user": {"login": BOT}},
    ]
    assert [c["id"] for c in guides_in(comments, CFG.bot_logins)] == [3]


async def test_upsert_ignores_a_bot_comment_quoting_the_marker():
    fake = FakeGitHub()
    answer = fake.add_comment(f"Thanks for the report. {MARKER} is our marker.")
    api = make(fake)
    assert await upsert_guide(api, 1, GUIDE, CFG.bot_logins) == "created"
    await api.aclose()
    assert next(c for c in fake.comments if c["id"] == answer)["body"].startswith("Thanks")
    assert fake.comments[-1]["body"] == GUIDE


async def test_content_with_the_marker_inside_still_starts_with_it():
    fake = FakeGitHub()
    api = make(fake)
    await upsert_guide(api, 1, f"block\n{MARKER}\nrest", CFG.bot_logins)
    await api.aclose()
    assert fake.comments[0]["body"] == f"{MARKER}\nblock\n{MARKER}\nrest"


def test_bot_comment_quoting_the_marker_is_not_an_own_event():
    bot = {"login": BOT}
    quoting = {"action": "created", "sender": bot, "comment": {"body": f"see {MARKER}"}}
    assert not is_own_event("issue_comment", quoting, {BOT})


async def test_dependency_pr_pinned_comment_starts_with_the_marker_then_the_block():
    fake = FakeGitHub(body="dependabot body")
    await converge(fake, author="dependabot[bot]")
    text = fake.comments[0]["body"]
    assert text.startswith(f"{MARKER}\n<!-- oct-status:v1") and text.count(MARKER) == 1
    assert "### Last action" not in text.split("<!-- /oct-status -->")[0]
    assert await converge(fake, author="dependabot[bot]") == []
