"""I5: a guide comment edited or deleted by a person is never adopted (V03).

Only a version of the guide that GitHub's edit history shows as written by our own accounts is taken over
(``changes.body.from`` of a single edit by a person); anything that cannot be verified starts from an empty
state (fail closed): no notices, no protected-path acknowledgement from that text.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace

import httpx

from oct_status.apply import MARKER
from oct_status.notices import encode

from .test_violations_events import ACTIVE, LEDGER, NOW, Repo, pr_event, run

SHA = "f" * 40
BOT = "oct-support"


class EditRepo(Repo):
    """Repo that answers the GraphQL edit history of comments (``userContentEdits``)."""

    def __init__(self) -> None:
        super().__init__()
        self.edits: dict[int, list[tuple[str, str]]] = {}  # comment id -> (editor login, __typename), oldest first
        self.history_fails = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/graphql") and b"userContentEdits" in request.content:
            if self.history_fails:
                return httpx.Response(502, json={})
            node_id = json.loads(request.content)["variables"]["id"]
            cid = int(node_id.removeprefix("IC_"))
            comment = next((c for cs in self.comments.values() for c in cs if c["id"] == cid), None)
            if comment is None:
                return httpx.Response(200, json={"data": {"node": None}})
            nodes = [
                {"createdAt": NOW.isoformat(), "editor": {"login": a, "__typename": t}}
                for a, t in self.edits.get(cid, [])
            ]
            node = {
                "body": comment["body"],
                "author": {"login": BOT, "__typename": "User"},
                "userContentEdits": {"nodes": nodes[-2:]},
            }
            return httpx.Response(200, json={"data": {"node": node}})
        return super().handler(request)


def guide_comment(repo: Repo, number: int) -> dict:
    return next(c for c in repo.comments[number] if c["body"].startswith(MARKER))


def data_of(body: str) -> dict:
    return json.loads(re.search(r"<!-- oct-next-data (.*) -->", body)[1])


def forged_from(body: str, by: str = "mallory") -> str:
    """The same guide with the notices removed and a forged protected-path acknowledgement."""
    data = data_of(body)
    data.pop("notices", None)
    data["paths_accepted"] = {"sha": SHA, "by": by, "ts": NOW.isoformat()}
    return re.sub(r"<!-- oct-next-data .* -->", lambda _: f"<!-- oct-next-data {encode(data)} -->", body)


def comment_event(action: str, comment: dict, before: str | None = None, sender: str = "mallory") -> dict:
    payload: dict = {
        "action": action,
        "issue": {"number": 10},
        "comment": {
            "id": comment["id"],
            "node_id": f"IC_{comment['id']}",
            "body": comment["body"],
            "user": {"login": BOT},
        },
        "sender": {"login": sender},
    }
    if before is not None:
        payload["changes"] = {"body": {"from": before}}
    return payload


def edit(repo: EditRepo, comment: dict, body: str, sender: str = "mallory") -> dict:
    """A person edits the comment: the history records the edit, the event carries the previous text."""
    before = comment["body"]
    comment["body"] = body
    repo.edits.setdefault(comment["id"], []).append((sender, "User"))
    return comment_event("edited", comment, before=before, sender=sender)


async def pr_with_notice() -> tuple[EditRepo, dict, str]:
    """PR #10 without a spec reference: its guide carries a V01 notice."""
    repo = EditRepo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    comment = guide_comment(repo, 10)
    repo.edits[comment["id"]] = [(BOT, "User")]  # the bot's own last write
    assert [n["rule"] for n in data_of(comment["body"])["notices"]] == ["V01"]
    return repo, comment, comment["body"]


def open_rules(body: str) -> list[str]:
    return sorted(n["rule"] for n in data_of(body).get("notices", []) if not n["resolved"])


async def test_edited_guide_is_restored_and_the_editor_gets_v03():
    repo, comment, original = await pr_with_notice()
    await run(repo, "issue_comment", edit(repo, comment, forged_from(original)))
    restored = guide_comment(repo, 10)["body"]
    assert open_rules(restored) == ["V01", "V03"] and "paths_accepted" not in data_of(restored)
    assert ("PATCH", f"/repos/o/r/issues/comments/{comment['id']}") in repo.writes
    v03 = [n for n in data_of(restored)["notices"] if n["rule"] == "V03"]
    assert v03[0]["user"] == "mallory" and "guide comment" in v03[0]["hint"]
    assert ("V03", "mallory") in [(e["rule"], e["user"]) for e in repo.ledger()]


async def test_edit_that_removes_the_marker_is_restored_as_well():
    repo, comment, original = await pr_with_notice()
    await run(repo, "issue_comment", edit(repo, comment, "all fine, nothing to see"))
    guides = [c for c in repo.comments[10] if c["body"].startswith(MARKER)]
    assert len(guides) == 1 and guides[0]["id"] == comment["id"]
    assert open_rules(guides[0]["body"]) == ["V01", "V03"]


async def test_dry_run_reports_and_never_adopts_the_edit(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo, comment, original = await pr_with_notice()
    forged = forged_from(original)
    event = edit(repo, comment, forged)
    writes = len(repo.writes)
    await run(repo, "issue_comment", event, dry_run=True)
    assert len(repo.writes) == writes and guide_comment(repo, 10)["body"] == forged
    text = summary.read_text(encoding="utf-8")
    assert "guide comment of #10 was edited by hand by `mallory`" in text and "V03" in text


async def test_deleted_guide_is_posted_again_from_an_empty_state():
    """A deleted comment's history cannot be read any more: nothing of its text is taken over."""
    repo, comment, original = await pr_with_notice()
    comment["body"] = forged_from(original, by="carol")
    repo.comments[10].remove(comment)
    await run(repo, "issue_comment", comment_event("deleted", comment))
    reposted = guide_comment(repo, 10)
    assert reposted["id"] != comment["id"] and open_rules(reposted["body"]) == ["V01", "V03"]
    assert "paths_accepted" not in data_of(reposted["body"])


async def test_deleting_a_corrupt_guide_starts_over_without_a_violation():
    """The documented recovery: a maintainer deletes a guide whose data is invalid."""
    repo, comment, original = await pr_with_notice()
    comment["body"] = re.sub(r"<!-- oct-next-data .* -->", "<!-- oct-next-data {broken -->", original)
    repo.comments[10].remove(comment)
    await run(repo, "issue_comment", comment_event("deleted", comment, sender="carol"))
    reposted = guide_comment(repo, 10)["body"]
    assert open_rules(reposted) == ["V01"] and all(e["rule"] != "V03" for e in repo.ledger())


async def test_edits_of_other_comments_are_no_guide_forgery_and_no_template_change():
    repo, comment, original = await pr_with_notice()
    other = {"id": 4242, "body": "## Notes\n- [ ] new item", "user": {"login": "alice"}}
    repo.comments[10].append(other)
    payload = comment_event("edited", other, before="## Old heading\n- [ ] gone item", sender="alice")
    payload["comment"]["user"] = {"login": "alice"}
    await run(repo, "issue_comment", payload)
    # The comment's old text is not the description: no V05 and no V03.
    assert open_rules(guide_comment(repo, 10)["body"]) == ["V01"]
    assert guide_comment(repo, 10)["body"] == original


async def test_strikes_inactive_restore_without_ledger():
    repo, comment, original = await pr_with_notice()
    inactive = replace(ACTIVE, strikes_enabled_from=None)
    await run(repo, "issue_comment", edit(repo, comment, forged_from(original)), cfg=inactive)
    assert open_rules(guide_comment(repo, 10)["body"]) == ["V01", "V03"]
    assert all(e["rule"] != "V03" for e in repo.ledger()) and LEDGER


async def test_refused_restore_is_a_warning_and_the_guide_is_still_written_from_its_own_state(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo, comment, original = await pr_with_notice()
    event = edit(repo, comment, forged_from(original), sender="not a login!")
    real, refused = repo.handler, []

    def refuse_first_patch(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and "/issues/comments/" in request.url.path and not refused:
            refused.append(request.url.path)
            return httpx.Response(403, json={})
        return real(request)

    repo.handler = refuse_first_patch  # type: ignore[method-assign]
    await run(repo, "issue_comment", event)
    assert refused and "not restored (HTTPStatusError)" in summary.read_text(encoding="utf-8")
    body = guide_comment(repo, 10)["body"]
    assert "paths_accepted" not in data_of(body) and "V01" in open_rules(body)


# --- laundering: only a version the edit history shows as ours is adopted ------------------------------


def acknowledged(body: str) -> bool:
    return "paths_accepted" in data_of(body)


async def test_single_edit_after_the_bots_write_adopts_the_previous_text():
    repo, comment, original = await pr_with_notice()
    await run(repo, "issue_comment", edit(repo, comment, "garbage"))
    restored = guide_comment(repo, 10)["body"]
    assert open_rules(restored) == ["V01", "V03"]
    assert ("PATCH", f"/repos/o/r/issues/comments/{comment['id']}") in repo.writes


async def test_double_edit_is_not_laundered_into_the_state():
    """Edit 1 forges an acknowledgement, edit 2 changes a word: edit 2's `from` (edit 1) is not ours."""
    repo, comment, original = await pr_with_notice()
    forged = forged_from(original)
    edit(repo, comment, forged)  # its event is lost
    await run(repo, "issue_comment", edit(repo, comment, forged.replace("Next steps", "Next step")))
    body = guide_comment(repo, 10)["body"]
    assert not acknowledged(body) and open_rules(body) == ["V01", "V03"]


async def test_late_event_of_an_earlier_edit_is_not_adopted():
    """The event of edit 1 arrives after edit 2: the current text is not the one the event names."""
    repo, comment, original = await pr_with_notice()
    first = edit(repo, comment, forged_from(original))
    first["changes"]["body"]["from"] = forged_from(original, by="carol")  # whatever it claims
    edit(repo, comment, "something else")
    await run(repo, "issue_comment", first)
    assert not acknowledged(guide_comment(repo, 10)["body"])


async def test_edit_then_delete_starts_from_an_empty_state():
    repo, comment, original = await pr_with_notice()
    edit(repo, comment, forged_from(original))  # its event is lost
    repo.comments[10].remove(comment)
    await run(repo, "issue_comment", comment_event("deleted", comment))
    body = guide_comment(repo, 10)["body"]
    assert not acknowledged(body) and open_rules(body) == ["V01", "V03"]


async def test_unreadable_edit_history_starts_from_an_empty_state():
    repo, comment, original = await pr_with_notice()
    laundered = forged_from(original, by="carol")
    comment["body"] = laundered  # pretend the bot wrote it; the history cannot confirm it
    repo.history_fails = True
    await run(repo, "issue_comment", edit(repo, comment, "x"))
    body = guide_comment(repo, 10)["body"]
    assert not acknowledged(body) and open_rules(body) == ["V01", "V03"]
    assert ("PATCH", f"/repos/o/r/issues/comments/{comment['id']}") in repo.writes


async def test_edit_whose_previous_version_is_a_persons_starts_empty_even_with_a_valid_text():
    repo, comment, original = await pr_with_notice()
    repo.edits[comment["id"]] = [(BOT, "User"), ("carol", "User")]  # carol wrote the current version
    comment["body"] = forged_from(original, by="carol")
    await run(repo, "issue_comment", edit(repo, comment, "x"))
    assert not acknowledged(guide_comment(repo, 10)["body"])


async def test_the_bots_own_edits_and_deletions_are_ignored():
    repo, comment, original = await pr_with_notice()
    writes = len(repo.writes)
    await run(repo, "issue_comment", comment_event("edited", comment, before=original, sender=BOT))
    await run(repo, "issue_comment", comment_event("deleted", comment, sender=BOT))
    assert len(repo.writes) == writes


async def test_edit_history_without_the_senders_edit_or_editor_starts_empty():
    """The newest edit is not the sender's (history lags or names nobody): not verifiable."""
    repo, comment, original = await pr_with_notice()
    comment["body"] = forged_from(original, by="carol")
    event = edit(repo, comment, "x")
    repo.edits[comment["id"]][-1] = ("", "User")  # a deleted account (ghost) or no editor information
    await run(repo, "issue_comment", event)
    assert not acknowledged(guide_comment(repo, 10)["body"])
