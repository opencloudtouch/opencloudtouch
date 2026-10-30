"""I5: a guide comment edited or deleted by a person is restored from its last own state, never adopted (V03)."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from oct_status.apply import MARKER
from oct_status.notices import encode

from .test_violations_events import ACTIVE, LEDGER, NOW, Repo, pr_event, run

SHA = "f" * 40


def guide_comment(repo: Repo, number: int) -> dict:
    return next(c for c in repo.comments[number] if c["body"].startswith(MARKER))


def data_of(body: str) -> dict:
    return json.loads(re.search(r"<!-- oct-next-data (.*) -->", body)[1])


def forged_from(body: str) -> str:
    """The same guide with the notices removed and a forged protected-path acknowledgement."""
    data = data_of(body)
    data.pop("notices", None)
    data["paths_accepted"] = {"sha": SHA, "by": "mallory", "ts": NOW.isoformat()}
    return re.sub(r"<!-- oct-next-data .* -->", lambda _: f"<!-- oct-next-data {encode(data)} -->", body)


def comment_event(action: str, comment: dict, before: str | None = None, sender: str = "mallory") -> dict:
    payload: dict = {
        "action": action,
        "issue": {"number": 10},
        "comment": {"id": comment["id"], "body": comment["body"], "user": {"login": "oct-support"}},
        "sender": {"login": sender},
    }
    if before is not None:
        payload["changes"] = {"body": {"from": before}}
    return payload


async def pr_with_notice() -> tuple[Repo, dict, str]:
    """PR #10 without a spec reference: its guide carries a V01 notice."""
    repo = Repo()
    repo.add_pr(10)
    await run(repo, "pull_request_target", pr_event(10))
    comment = guide_comment(repo, 10)
    assert [n["rule"] for n in data_of(comment["body"])["notices"]] == ["V01"]
    return repo, comment, comment["body"]


def open_rules(body: str) -> list[str]:
    return sorted(n["rule"] for n in data_of(body).get("notices", []) if not n["resolved"])


async def test_edited_guide_is_restored_and_the_editor_gets_v03():
    repo, comment, original = await pr_with_notice()
    comment["body"] = forged_from(original)
    await run(repo, "issue_comment", comment_event("edited", comment, before=original))
    restored = guide_comment(repo, 10)["body"]
    assert open_rules(restored) == ["V01", "V03"] and "paths_accepted" not in data_of(restored)
    assert ("PATCH", f"/repos/o/r/issues/comments/{comment['id']}") in repo.writes
    v03 = [n for n in data_of(restored)["notices"] if n["rule"] == "V03"]
    assert v03[0]["user"] == "mallory" and "guide comment" in v03[0]["hint"]
    assert ("V03", "mallory") in [(e["rule"], e["user"]) for e in repo.ledger()]


async def test_edit_that_removes_the_marker_is_restored_as_well():
    repo, comment, original = await pr_with_notice()
    comment["body"] = "all fine, nothing to see"
    await run(repo, "issue_comment", comment_event("edited", comment, before=original))
    guides = [c for c in repo.comments[10] if c["body"].startswith(MARKER)]
    assert len(guides) == 1 and guides[0]["id"] == comment["id"]
    assert open_rules(guides[0]["body"]) == ["V01", "V03"]


async def test_dry_run_reports_and_never_adopts_the_edit(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo, comment, original = await pr_with_notice()
    forged = forged_from(original)
    comment["body"] = forged
    writes = len(repo.writes)
    await run(repo, "issue_comment", comment_event("edited", comment, before=original), dry_run=True)
    assert len(repo.writes) == writes and guide_comment(repo, 10)["body"] == forged
    text = summary.read_text(encoding="utf-8")
    assert "guide comment of #10 was edited by hand by `mallory`" in text and "V03" in text


async def test_deleted_guide_is_posted_again_with_its_state():
    repo, comment, original = await pr_with_notice()
    repo.comments[10].remove(comment)
    await run(repo, "issue_comment", comment_event("deleted", comment))
    reposted = guide_comment(repo, 10)
    assert reposted["id"] != comment["id"] and open_rules(reposted["body"]) == ["V01", "V03"]


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
    comment["body"] = forged_from(original)
    inactive = replace(ACTIVE, strikes_enabled_from=None)
    await run(repo, "issue_comment", comment_event("edited", comment, before=original), cfg=inactive)
    assert open_rules(guide_comment(repo, 10)["body"]) == ["V01", "V03"]
    assert all(e["rule"] != "V03" for e in repo.ledger()) and LEDGER


async def test_refused_restore_is_a_warning_and_the_guide_is_still_written_from_its_own_state(monkeypatch, tmp_path):
    import httpx

    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo, comment, original = await pr_with_notice()
    comment["body"] = forged_from(original)
    real, refused = repo.handler, []

    def refuse_first_patch(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and "/issues/comments/" in request.url.path and not refused:
            refused.append(request.url.path)
            return httpx.Response(403, json={})
        return real(request)

    repo.handler = refuse_first_patch  # type: ignore[method-assign]
    event = comment_event("edited", comment, before=original, sender="not a login!")
    await run(repo, "issue_comment", event)
    assert refused and "not restored (HTTPStatusError)" in summary.read_text(encoding="utf-8")
    body = guide_comment(repo, 10)["body"]
    assert "paths_accepted" not in data_of(body) and "V01" in open_rules(body)
