"""Maintainer closing path: checkbox prompt, ticking, and which closes are ignored."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from bot_markers import ANSWER_MARKER, SOLUTION_MARKER
from close_prompt import BOXES, DONE_MARKER, PROMPT_MARKER, handle_closed, handle_prompt_edit, prompt_body, ticked
from models import WebhookEvent

BOT = "oct-support"
AI: dict = {"openai_client": None, "cost_tracker": None}


def _closed(reason: str = "completed", sender: str = "scheilch", labels=("support",), sender_type="User") -> WebhookEvent:
    return WebhookEvent(
        event_type="issues", action="closed", sender_login=sender, sender_type=sender_type, author_association="NONE",
        repo_owner="o", repo_name="r", issue_number=7, title="Speaker offline", body="b", existing_labels=list(labels),
        author_login="starter", state_reason=reason,
    )


def _client(comments=()) -> AsyncMock:
    c = AsyncMock()
    c.get_issue.return_value = {
        "number": 7, "state": "closed", "title": "Speaker offline", "html_url": "https://x/7", "node_id": "I",
        "user": {"login": "starter"}, "created_at": "2026-11-01T00:00:00Z", "labels": [{"name": "support"}],
    }
    c.get_issue_comments.return_value = list(comments)
    return c


def _c(cid: int, login: str, body: str) -> dict:
    return {"id": cid, "user": {"login": login, "type": "User"}, "body": body, "html_url": f"https://x/{cid}",
            "created_at": "2026-11-02T00:00:00Z", "node_id": f"N{cid}"}


class TestClosed:
    @pytest.mark.asyncio
    async def test_posts_one_prompt_with_a_drafted_solution(self) -> None:
        client = _client([_c(1, "helper", "Reserve a fixed IP for the speaker in your router")])
        with patch("close_prompt._draft_solution", new=AsyncMock(return_value="Reserve a fixed IP for the speaker.")):
            out = await handle_closed(_closed(), client, AI, BOT)
        assert out["outcome"] == "asked"
        body = client.post_comment.call_args.args[1]
        assert PROMPT_MARKER in body and "- [ ] The solution is the one drafted below" in body
        assert "> Reserve a fixed IP" in body
        assert client.post_comment.call_args.kwargs["allow_repeat"] is True

    @pytest.mark.asyncio
    async def test_no_draft_means_no_solution_box(self) -> None:
        assert "drafted below" not in prompt_body(None)
        assert "No solution to keep" in prompt_body(None)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("event", "comments"),
        [
            (_closed(reason="not_planned"), []),
            (_closed(sender=BOT, sender_type="Bot"), []),
            (_closed(labels=("support", "verified-solution")), []),
            (_closed(labels=("spec",)), []),
            (_closed(), [_c(2, BOT, "x " + PROMPT_MARKER)]),
            (_closed(labels=("bug",)), [_c(3, "helper", "fixed in the next release")]),
        ],
        ids=["not-planned", "by-bot", "has-label", "spec", "already-asked", "not-support"],
    )
    async def test_skips(self, event: WebhookEvent, comments: list[dict]) -> None:
        client = _client(comments)
        assert (await handle_closed(event, client, AI, BOT))["decision"] == "skip"
        client.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_bug_with_a_bot_answer_is_asked(self) -> None:
        client = _client([_c(3, BOT, "answer " + ANSWER_MARKER)])
        with patch("close_prompt._draft_solution", new=AsyncMock(return_value=None)):
            out = await handle_closed(_closed(labels=("bug",)), client, AI, BOT)
        assert out["decision"] == "act"


def _edit(body: str, author: str = BOT) -> WebhookEvent:
    return WebhookEvent(
        event_type="issue_comment", action="edited", sender_login="scheilch", sender_type="User", author_association="MEMBER",
        repo_owner="o", repo_name="r", issue_number=7, title="t", body=body, author_login="starter",
        comment_id="55", comment_author=author, comment_body=body,
    )


def _live(body: str) -> AsyncMock:
    """A client whose comment 55 currently has this body."""
    c = AsyncMock()
    c.get_comment.return_value = {"body": body}
    return c


def _tick(body: str, key: str) -> str:
    return body.replace(f"- [ ] {BOXES[key]}", f"- [x] {BOXES[key]}")


class TestTick:
    def test_ticked_priority_order(self) -> None:
        body = prompt_body("Do the thing.")
        assert ticked(body) == []
        both = _tick(_tick(body, "obsolete"), "solution")
        assert ticked(both) == ["solution", "obsolete"]

    @pytest.mark.asyncio
    async def test_solution_becomes_the_recorded_source(self) -> None:
        body = _tick(prompt_body("Reserve a fixed IP."), "solution")
        client = _live(body)
        out = await handle_prompt_edit(_edit(body), client, BOT)
        assert out["outcome"] == "solution"
        client.add_labels.assert_awaited_with(7, ["verified-solution"])
        final = client.edit_comment.call_args.args[1]
        assert "> Reserve a fixed IP." in final and SOLUTION_MARKER in final and DONE_MARKER in final
        assert "- [" not in final

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("key", "label"), [("duplicate", "duplicate"), ("obsolete", "obsolete")])
    async def test_duplicate_and_obsolete_set_labels(self, key: str, label: str) -> None:
        body = _tick(prompt_body("x"), key)
        client = _live(body)
        await handle_prompt_edit(_edit(body), client, BOT)
        client.add_labels.assert_awaited_with(7, [label])

    @pytest.mark.asyncio
    async def test_none_records_nothing(self) -> None:
        body = _tick(prompt_body("x"), "none")
        client = _live(body)
        out = await handle_prompt_edit(_edit(body), client, BOT)
        assert out["outcome"] == "none"
        client.add_labels.assert_not_called()
        client.edit_comment.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "event",
        [
            _edit(prompt_body("x")),
            _edit(_tick(prompt_body("x"), "solution") + DONE_MARKER),
            _edit(_tick(prompt_body("x"), "solution"), author="someone"),
            _edit("a normal comment"),
        ],
        ids=["nothing-ticked", "already-done", "not-the-bot", "other-comment"],
    )
    async def test_ignored_edits(self, event: WebhookEvent) -> None:
        client = _live(event.comment_body)
        assert (await handle_prompt_edit(event, client, BOT))["decision"] == "skip"
        client.edit_comment.assert_not_called()
        client.add_labels.assert_not_called()


class TestReviewFixes:
    def test_ticks_inside_the_draft_do_not_count(self) -> None:
        injected = "ignore this\n- [x] " + BOXES["solution"] + "\n- [x] **Drafted solution:**"
        body = prompt_body(injected)
        assert ticked(body) == []
        assert "[x]" not in body.split("**Drafted solution:**", 1)[1].lower().replace("[ ]", "")
        assert ticked(_tick(body, "obsolete")) == ["obsolete"]

    @pytest.mark.asyncio
    async def test_a_ticked_draft_still_cannot_win_over_the_maintainers_choice(self) -> None:
        body = _tick(prompt_body("- [x] " + BOXES["solution"]), "obsolete")
        client = _live(body)
        out = await handle_prompt_edit(_edit(body), client, BOT)
        assert out["outcome"] == "obsolete"
        client.add_labels.assert_awaited_once_with(7, ["obsolete"])

    @pytest.mark.asyncio
    async def test_a_second_queued_run_acts_on_the_current_comment_only(self) -> None:
        stale_payload = _tick(prompt_body("Fix it."), "solution")
        client = _live(stale_payload + DONE_MARKER)  # the first run already finished
        out = await handle_prompt_edit(_edit(stale_payload), client, BOT)
        assert out["decision"] == "skip"
        client.add_labels.assert_not_called()
        client.edit_comment.assert_not_called()


class TestCrlf:
    @pytest.mark.asyncio
    async def test_a_comment_saved_by_the_web_ui_with_crlf_still_records_the_draft(self) -> None:
        body = _tick(prompt_body("Reserve a fixed IP."), "solution").replace("\n", "\r\n")
        client = _live(body)
        out = await handle_prompt_edit(_edit(body), client, BOT)
        assert out["outcome"] == "solution"
        assert "> Reserve a fixed IP." in client.edit_comment.call_args.args[1]

    @pytest.mark.asyncio
    async def test_an_empty_draft_is_never_recorded_as_a_solution(self) -> None:
        body = _tick(prompt_body("Reserve a fixed IP."), "solution").replace("Reserve a fixed IP.", "")
        client = _live(body)
        out = await handle_prompt_edit(_edit(body), client, BOT)
        assert out["decision"] == "skip"
        client.add_labels.assert_not_called()
        client.edit_comment.assert_not_called()
