"""Follow-up cases, timing and the reply handler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from bot_markers import ANSWER_MARKER, SOLUTION_MARKER
from followup import (
    DEFAULTS,
    ECHO_MARKER,
    Comment,
    Thread,
    decode_marker,
    encode_marker,
    plan,
)
from models import WebhookEvent
from reply import deterministic, handle_reply

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
BOT = "oct-support"
LONG = "a long enough comment body here"


def _c(cid: str, author: str, body: str = LONG, days_ago: float = 5.0, kind: str = "User") -> Comment:
    return Comment(cid, author, kind, body, f"https://x/{cid}", NOW - timedelta(days=days_ago), node_id=f"N{cid}")


def _thread(comments=(), labels=("support",), created_days_ago: float = 10, kind: str = "issue") -> Thread:
    return Thread(kind, 7, "D_7", "Speaker offline", "https://x/7", "starter", NOW - timedelta(days=created_days_ago),
                  labels=set(labels), answerable=True, comments=list(comments))


AI_NONE: dict = {"openai_client": None, "cost_tracker": None}


class TestPlan:
    @pytest.mark.asyncio
    async def test_bot_notices_without_answer_marker_are_no_candidates(self) -> None:
        t = _thread([_c("1", BOT, "You exceeded the issue limit, please wait", days_ago=4), _c("2", "helper", days_ago=4)])
        out = await plan(t, BOT, NOW, DEFAULTS, AI_NONE)
        assert decode_marker(out["body"])["ids"] == ["2"]

    @pytest.mark.asyncio
    async def test_case1_lists_candidates_after_three_days(self) -> None:
        t = _thread([_c("1", "helper", days_ago=4), _c("2", BOT, ANSWER_MARKER + " bot answer text long enough", days_ago=4)])
        out = await plan(t, BOT, NOW, DEFAULTS, AI_NONE)
        assert out["case"] == 1
        assert "**A** ([comment](https://x/1))" in out["body"]
        assert "**B**" in out["body"] and "**H**: not solved" in out["body"]
        assert decode_marker(out["body"]) == {"case": 1, "ids": ["1", "2"]}

    @pytest.mark.asyncio
    async def test_case1_too_early(self) -> None:
        t = _thread([_c("1", "helper", days_ago=1)])
        assert await plan(t, BOT, NOW, DEFAULTS, AI_NONE) is None

    @pytest.mark.asyncio
    async def test_case2_label_after_three_days_question_after_seven(self) -> None:
        out = await plan(_thread(created_days_ago=4), BOT, NOW, DEFAULTS, AI_NONE)
        assert out == {"label": True, "body": None, "case": 0, "due": False}
        out = await plan(_thread(created_days_ago=8), BOT, NOW, DEFAULTS, AI_NONE)
        assert out["label"] and out["case"] == 2 and "Did you solve this" in out["body"]
        assert "**A**" not in out["body"]

    @pytest.mark.asyncio
    async def test_case3_offers_the_claimed_fix(self) -> None:
        t = _thread([_c("1", "starter", "I replaced the cable and it works now", days_ago=8)], created_days_ago=9)
        with patch("followup._ai_json", new=AsyncMock(return_value={"fix": "replaced the cable"})):
            out = await plan(t, BOT, NOW, DEFAULTS, AI_NONE)
        assert out["case"] == 3 and "replaced the cable" in out["body"]
        assert decode_marker(out["body"])["fix"] == "replaced the cable"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "thread",
        [
            _thread(labels=("spec",), created_days_ago=20),
            _thread(labels=("verified-solution", "support"), created_days_ago=20),
            _thread(labels=("bug",), created_days_ago=20),
            _thread(created_days_ago=90),
            _thread([_c("9", BOT, "x " + encode_marker(2, []), days_ago=8)], created_days_ago=20),
        ],
        ids=["spec", "verified", "not-support", "too-old", "already-followed-up"],
    )
    async def test_not_eligible(self, thread: Thread) -> None:
        assert await plan(thread, BOT, NOW, DEFAULTS, AI_NONE) is None

    @pytest.mark.asyncio
    async def test_bug_thread_with_bot_answer_is_eligible(self) -> None:
        t = _thread([_c("1", BOT, ANSWER_MARKER + " long enough bot answer", days_ago=5)], labels=("bug",))
        assert (await plan(t, BOT, NOW, DEFAULTS, AI_NONE))["case"] == 1

    def test_marker_cannot_contain_a_comment_terminator(self) -> None:
        marker = encode_marker(3, [], "use --force flag")
        assert marker.count("--") == 2  # only the opening and closing delimiters
        assert decode_marker(marker)["fix"] == "use - -force flag"


class TestDeterministic:
    @pytest.mark.parametrize(
        ("reply", "outcome", "letters"),
        [("B", "solved", ["B"]), ("b and f", "solved", ["B", "F"]), ("H", "not_solved", []), ("G", "unclear", [])],
    )
    def test_case1_letters(self, reply: str, outcome: str, letters: list[str]) -> None:
        r = deterministic(reply, 1)
        assert (r["outcome"], r["letters"]) == (outcome, letters)

    def test_case2_yes_no(self) -> None:
        assert deterministic("yes, updated the firmware", 2)["outcome"] == "solved"
        assert deterministic("no", 2)["outcome"] == "not_solved"
        assert deterministic("maybe later", 2)["outcome"] == "unclear"


def _issue_event(body: str, cid: str = "30", sender: str = "starter") -> WebhookEvent:
    return WebhookEvent(
        event_type="issue_comment", action="created", sender_login=sender, sender_type="User",
        author_association="NONE", repo_owner="o", repo_name="r", issue_number=7, title="t", body=body,
        author_login="starter", comment_id=cid, comment_author=sender, comment_body=body,
    )


def _issue_client(comments: list[dict]) -> AsyncMock:
    c = AsyncMock()
    c.get_issue.return_value = {
        "number": 7, "state": "open", "title": "t", "html_url": "https://x/7", "node_id": "I",
        "user": {"login": "starter"}, "created_at": "2026-11-01T00:00:00Z", "labels": [{"name": "support"}],
    }
    c.get_issue_comments.return_value = comments
    return c


def _api(cid: int, login: str, body: str) -> dict:
    return {
        "id": cid, "user": {"login": login, "type": "User"}, "body": body, "html_url": f"https://x/{cid}",
        "created_at": f"2026-11-{cid:02d}T00:00:00Z", "node_id": f"N{cid}",
    }


FOLLOWUP = "Did one help?\n" + encode_marker(1, ["10", "11"])


class TestReply:
    @pytest.mark.asyncio
    async def test_letter_solves_labels_and_closes(self) -> None:
        client = _issue_client([
            _api(10, "helper", "Reserve a fixed IP for the speaker"), _api(11, "other", "Reboot the router twice"),
            _api(20, BOT, FOLLOWUP), _api(30, "starter", "B"),
        ])
        out = await handle_reply(_issue_event("B"), client, AI_NONE, BOT)
        assert out["outcome"] == "solved" and out["letters"] == ["B"]
        echo = client.post_comment.call_args.args[1]
        assert "Reboot the router twice" in echo and SOLUTION_MARKER in echo and ECHO_MARKER in echo
        assert client.post_comment.call_args.kwargs["allow_repeat"] is True
        client.add_labels.assert_awaited_with(7, ["verified-solution"])
        client.close_issue.assert_awaited_with(7, "completed")

    @pytest.mark.asyncio
    async def test_not_solved_labels_needs_human_and_stays_open(self) -> None:
        client = _issue_client([_api(10, "helper", "x" * 30), _api(20, BOT, FOLLOWUP), _api(30, "starter", "H")])
        out = await handle_reply(_issue_event("H"), client, AI_NONE, BOT)
        assert out["outcome"] == "not_solved"
        client.add_labels.assert_awaited_with(7, ["needs-human"])
        client.close_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_unclear_only_asks_again(self) -> None:
        client = _issue_client([_api(20, BOT, FOLLOWUP), _api(30, "starter", "hmm")])
        with patch("reply._ai_json", new=AsyncMock(return_value=None)):
            out = await handle_reply(_issue_event("hmm"), client, AI_NONE, BOT)
        assert out["outcome"] == "unclear"
        client.add_labels.assert_not_called()
        client.close_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_free_text_via_ai(self) -> None:
        text = "none of them, I swapped the cable"
        client = _issue_client([_api(10, "helper", "x" * 30), _api(20, BOT, FOLLOWUP), _api(30, "starter", text)])
        ai = {"outcome": "solved", "letters": [], "solution": "swapped the cable"}
        with patch("reply._ai_json", new=AsyncMock(return_value=ai)):
            out = await handle_reply(_issue_event(text), client, AI_NONE, BOT)
        assert out["outcome"] == "solved"
        assert "swapped the cable" in client.post_comment.call_args.args[1]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("comments", "event"),
        [
            ([_api(20, BOT, FOLLOWUP), _api(30, "starter", "B")], _issue_event("B", sender="someone")),
            ([_api(30, "starter", "B")], _issue_event("B")),
            ([_api(20, BOT, FOLLOWUP), _api(21, BOT, "x " + ECHO_MARKER), _api(30, "starter", "B")], _issue_event("B", cid="25")),
        ],
        ids=["not-the-starter", "no-follow-up", "already-handled"],
    )
    async def test_skips(self, comments: list[dict], event: WebhookEvent) -> None:
        client = _issue_client(comments)
        assert (await handle_reply(event, client, AI_NONE, BOT))["decision"] == "skip"
        client.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_discussion_marks_the_chosen_answer_and_closes(self) -> None:
        client = AsyncMock()
        client.get_discussion.return_value = {
            "id": "D_7", "number": 7, "title": "t", "url": "https://x/7", "createdAt": "2026-11-01T00:00:00Z",
            "closed": False, "author": {"login": "starter"}, "category": {"isAnswerable": True},
            "comments": {"nodes": [
                {"id": "C10", "url": "u10", "body": "Reserve a fixed IP for the speaker",
                 "createdAt": "2026-11-02T00:00:00Z", "author": {"login": "helper"}},
                {"id": "C20", "url": "u20", "body": "q\n" + encode_marker(1, ["C10"]),
                 "createdAt": "2026-11-03T00:00:00Z", "author": {"login": BOT}},
                {"id": "C30", "url": "u30", "body": "A", "createdAt": "2026-11-04T00:00:00Z",
                 "author": {"login": "starter"}},
            ]},
        }
        client.post_discussion_comment.return_value = "C_echo"
        ev = WebhookEvent(
            event_type="discussion_comment", action="created", sender_login="starter", sender_type="User",
            author_association="NONE", repo_owner="o", repo_name="r", issue_number=7, title="t", body="A",
            is_discussion=True, author_login="starter", node_id="D_7", comment_id="C30", comment_body="A",
        )
        out = await handle_reply(ev, client, AI_NONE, BOT)
        assert out["outcome"] == "solved"
        client.mark_discussion_answer.assert_awaited_with("C10")
        client.close_discussion.assert_awaited_with("D_7")


class TestRunFollowups:
    @pytest.mark.asyncio
    async def test_posts_labels_and_respects_the_cap(self) -> None:
        from followup_main import run_followups

        def issue(n: int) -> dict:
            return {"number": n, "title": "t", "html_url": f"https://x/{n}", "node_id": f"I{n}", "user": {"login": "starter"},
                    "created_at": "2026-11-01T00:00:00Z", "labels": [{"name": "support"}]}

        client = AsyncMock()
        client.list_open_issues.return_value = [issue(n) for n in range(1, 8)]
        client.get_issue_comments.return_value = []
        client.list_open_discussions.return_value = []
        out = await run_followups(client, AI_NONE, {"followup_max_per_run": 2}, BOT, datetime(2026, 11, 20, tzinfo=timezone.utc))
        assert len(out) == 7 and client.add_labels.await_count == 7
        assert client.post_comment.await_count == 2
        assert sum(1 for e in out if e.get("deferred")) == 5
        assert client.post_comment.call_args.kwargs["allow_repeat"] is True


class TestReviewFixes:
    @pytest.mark.asyncio
    async def test_echo_names_the_letters_the_author_gave(self) -> None:
        client = _issue_client([
            _api(10, "a", "first helpful reply text here"), _api(11, "b", "second helpful reply text here"),
            _api(12, "c", "third helpful reply text here"), _api(20, BOT, "q " + encode_marker(1, ["10", "11", "12"])),
            _api(30, "starter", "C"),
        ])
        await handle_reply(_issue_event("C"), client, AI_NONE, BOT)
        echo = client.post_comment.call_args.args[1]
        assert "[C](https://x/12)" in echo and "[A]" not in echo

    @pytest.mark.asyncio
    async def test_a_closed_solved_issue_can_be_corrected(self) -> None:
        echo_comment = "Understood: [A] solved it.\n" + SOLUTION_MARKER + ECHO_MARKER
        client = _issue_client([
            _api(10, "helper", "x" * 30), _api(20, BOT, FOLLOWUP), _api(21, BOT, echo_comment), _api(30, "starter", "H"),
        ])
        client.get_issue.return_value["state"] = "closed"
        out = await handle_reply(_issue_event("H"), client, AI_NONE, BOT)
        assert out["outcome"] == "not_solved"
        client.remove_label.assert_any_await(7, "verified-solution")
        client.reopen_issue.assert_awaited_once_with(7)

    @pytest.mark.asyncio
    async def test_a_closed_issue_without_an_echo_is_ignored(self) -> None:
        client = _issue_client([_api(20, BOT, FOLLOWUP), _api(30, "starter", "B")])
        client.get_issue.return_value["state"] = "closed"
        assert (await handle_reply(_issue_event("B"), client, AI_NONE, BOT))["decision"] == "skip"

    def test_discussion_replies_inside_the_follow_up_are_part_of_the_thread(self) -> None:
        from followup import discussion_to_thread

        d = {
            "id": "D", "number": 7, "title": "t", "url": "u", "createdAt": "2026-11-01T00:00:00Z", "isAnswered": False,
            "author": {"login": "starter"}, "category": {"isAnswerable": True}, "labels": {"nodes": [{"name": "needs-human"}]},
            "comments": {"nodes": [{
                "id": "C20", "url": "u20", "body": "q " + encode_marker(1, []), "createdAt": "2026-11-03T00:00:00Z",
                "author": {"login": BOT, "__typename": "User"},
                "replies": {"nodes": [{"id": "R1", "url": "ur", "body": "B", "createdAt": "2026-11-04T00:00:00Z",
                                       "author": {"login": "starter", "__typename": "User"}}]},
            }]},
        }
        thread = discussion_to_thread(d)
        assert [c.id for c in thread.comments] == ["C20", "R1"]
        assert thread.labels == {"needs-human"}

    @pytest.mark.asyncio
    async def test_answered_or_labelled_discussions_get_no_follow_up(self) -> None:
        t = _thread(kind="discussion", created_days_ago=20)
        t.answered = True
        assert await plan(t, BOT, NOW, DEFAULTS, AI_NONE) is None
        t2 = _thread(kind="discussion", labels=("needs-human",), created_days_ago=20)
        assert await plan(t2, BOT, NOW, DEFAULTS, AI_NONE) is None

    @pytest.mark.asyncio
    async def test_a_maintainer_closure_after_a_not_solved_echo_stays(self) -> None:
        echo_comment = "Understood: not solved.\n" + ECHO_MARKER
        client = _issue_client([_api(20, BOT, FOLLOWUP), _api(21, BOT, echo_comment), _api(30, "starter", "H")])
        client.get_issue.return_value["state"] = "closed"
        assert (await handle_reply(_issue_event("H"), client, AI_NONE, BOT))["decision"] == "skip"
        client.reopen_issue.assert_not_called()


class TestSecondReviewFixes:
    def test_a_bare_yes_is_not_a_solution(self) -> None:
        assert deterministic("yes", 2) == {"outcome": "unclear", "letters": [], "solution": None}
        assert deterministic("yes", 3) == {"outcome": "solved", "letters": [], "solution": None}
        assert deterministic("Yes, updated the firmware", 2)["solution"] == "updated the firmware"

    @pytest.mark.asyncio
    async def test_a_bare_yes_in_case_3_keeps_the_fix_of_the_marker(self) -> None:
        followup = "q " + encode_marker(3, [], "replaced the cable")
        client = _issue_client([_api(20, BOT, followup), _api(30, "starter", "yes")])
        out = await handle_reply(_issue_event("yes"), client, AI_NONE, BOT)
        assert out["outcome"] == "solved"
        assert "**Solution:** replaced the cable" in client.post_comment.call_args.args[1]

    @pytest.mark.asyncio
    async def test_comments_after_a_not_solved_echo_are_left_to_the_maintainer(self) -> None:
        echo = "Understood: not solved yet.\n" + ECHO_MARKER
        client = _issue_client([_api(20, BOT, FOLLOWUP), _api(21, BOT, echo), _api(30, "starter", "here are my logs")])
        assert (await handle_reply(_issue_event("here are my logs"), client, AI_NONE, BOT))["decision"] == "skip"
        client.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_first_unclear_echo_asks_again_but_the_second_is_the_last(self) -> None:
        from reply import UNCLEAR_MARKER

        unclear = "I could not tell.\n" + UNCLEAR_MARKER + "\n" + ECHO_MARKER
        one = _issue_client([_api(20, BOT, FOLLOWUP), _api(21, BOT, unclear), _api(30, "starter", "B")])
        assert (await handle_reply(_issue_event("B"), one, AI_NONE, BOT))["decision"] == "act"
        two = _issue_client([_api(20, BOT, FOLLOWUP), _api(21, BOT, unclear), _api(22, BOT, unclear), _api(30, "starter", "hmm")])
        assert (await handle_reply(_issue_event("hmm"), two, AI_NONE, BOT))["decision"] == "skip"

    @pytest.mark.asyncio
    async def test_a_discussion_category_without_answers_is_still_closed(self) -> None:
        client = AsyncMock()
        client.get_discussion.return_value = {
            "id": "D_7", "number": 7, "title": "t", "url": "u", "createdAt": "2026-11-01T00:00:00Z",
            "closed": False, "author": {"login": "starter"}, "category": {"isAnswerable": False},
            "comments": {"nodes": [
                {"id": "C10", "url": "u10", "body": "Reserve a fixed IP for the speaker", "createdAt": "2026-11-02T00:00:00Z",
                 "author": {"login": "helper"}},
                {"id": "C20", "url": "u20", "body": "q\n" + encode_marker(1, ["C10"]), "createdAt": "2026-11-03T00:00:00Z",
                 "author": {"login": BOT}},
                {"id": "C30", "url": "u30", "body": "A", "createdAt": "2026-11-04T00:00:00Z", "author": {"login": "starter"}},
            ]},
        }
        client.post_discussion_comment.return_value = "C_echo"
        ev = WebhookEvent(
            event_type="discussion_comment", action="created", sender_login="starter", sender_type="User",
            author_association="NONE", repo_owner="o", repo_name="r", issue_number=7, title="t", body="A",
            is_discussion=True, author_login="starter", node_id="D_7", comment_id="C30", comment_body="A",
        )
        await handle_reply(ev, client, AI_NONE, BOT)
        client.mark_discussion_answer.assert_not_called()
        client.close_discussion.assert_awaited_with("D_7")

    @pytest.mark.asyncio
    async def test_no_ai_is_spent_on_follow_ups_past_the_per_run_limit(self) -> None:
        from followup_main import run_followups

        def issue(n: int) -> dict:
            return {"number": n, "title": "t", "html_url": f"https://x/{n}", "node_id": f"I{n}", "user": {"login": "starter"},
                    "created_at": "2026-11-01T00:00:00Z", "labels": [{"name": "support"}]}

        client = AsyncMock()
        client.list_open_issues.return_value = [issue(n) for n in range(1, 6)]
        client.get_issue_comments.return_value = []
        client.list_open_discussions.return_value = []
        with patch("followup.claimed_fix", new=AsyncMock(return_value=None)) as spent:
            out = await run_followups(client, AI_NONE, {"followup_max_per_run": 2}, BOT, datetime(2026, 11, 20, tzinfo=timezone.utc))
        assert spent.await_count == 2
        assert sum(1 for e in out if e.get("deferred")) == 3
