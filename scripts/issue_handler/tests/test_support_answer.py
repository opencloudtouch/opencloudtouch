"""Delayed answer: pre-checks, retrieval, dry-run and comment markers."""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bot_markers import ANSWER_MARKER, finalize_comment
from dry_run import DryRunClient
from models import WebhookEvent
from precheck import delay_seconds, early_skip_reason, recheck
from retrieval import Source, find_sources, relevance, tokens


def _event(**kw) -> WebhookEvent:
    d = dict(
        event_type="issues", action="opened", sender_login="u", sender_type="User", author_association="NONE",
        repo_owner="o", repo_name="r", issue_number=7, title="Speaker offline", body="x", author_login="starter",
    )
    d.update(kw)
    return WebhookEvent(**d)


def _client(state="open", labels=(), comments=()) -> AsyncMock:
    c = AsyncMock()
    c.get_issue.return_value = {"state": state, "labels": [{"name": n} for n in labels]}
    c.get_issue_comments.return_value = list(comments)
    return c


def _comment(login: str, body: str = "hi", kind: str = "User") -> dict:
    return {"user": {"login": login, "type": kind}, "body": body}


class TestEarlySkip:
    def test_edited_and_comment_events_never_answer(self) -> None:
        assert early_skip_reason(_event(action="edited"))
        assert early_skip_reason(_event(event_type="issue_comment", action="created"))
        assert early_skip_reason(_event()) is None
        assert early_skip_reason(_event(event_type="discussion", is_discussion=True, action="created")) is None


class TestDelay:
    def test_within_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OCT_BOT_DELAY_MIN")
        monkeypatch.delenv("OCT_BOT_DELAY_MAX")
        for _ in range(20):
            assert 300 <= delay_seconds({}, random.Random()) <= 600

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OCT_BOT_DELAY_MIN", "1")
        monkeypatch.setenv("OCT_BOT_DELAY_MAX", "1")
        assert delay_seconds({}) == 1


class TestRecheck:
    @pytest.mark.asyncio
    async def test_quiet_thread_may_be_answered(self) -> None:
        assert await recheck(_event(), _client(comments=[_comment("starter")]), "oct-support") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("client", "reason"),
        [
            (_client(state="closed"), "closed"),
            (_client(labels=["spec"]), "label spec"),
            (_client(labels=["needs-human"]), "label needs-human"),
            (_client(comments=[_comment("oct-support")]), "already answered"),
            (_client(comments=[_comment("x", ANSWER_MARKER)]), "already answered"),
            (_client(comments=[_comment("maintainer")]), "human already replied"),
        ],
    )
    async def test_skips(self, client: AsyncMock, reason: str) -> None:
        assert reason.split()[-1] in (await recheck(_event(), client, "oct-support") or "")

    @pytest.mark.asyncio
    async def test_other_bots_do_not_count_as_humans(self) -> None:
        client = _client(comments=[_comment("dependabot", kind="Bot")])
        assert await recheck(_event(), client, "oct-support") is None

    @pytest.mark.asyncio
    async def test_discussion(self) -> None:
        client = AsyncMock()
        client.get_discussion.return_value = {
            "closed": False, "labels": {"nodes": []},
            "comments": {"nodes": [{"author": {"login": "someone"}, "body": "b"}]},
        }
        ev = _event(event_type="discussion", is_discussion=True, action="created")
        assert "human" in (await recheck(ev, client, "oct-support") or "")
        client.get_discussion.return_value["closed"] = True
        assert "closed" in (await recheck(ev, client, "oct-support") or "")


class TestRetrieval:
    def test_relevance_needs_three_shared_terms(self) -> None:
        q = tokens("speaker offline after router restart wifi")
        assert relevance(q, tokens("speaker wifi")) == 0.0
        assert relevance(q, tokens("speaker offline after router restart")) > 0.5

    @pytest.mark.asyncio
    async def test_only_verified_threads_with_a_solution_are_sources(self, tmp_path: Path) -> None:
        client = AsyncMock()
        client.search_labelled_threads.return_value = [
            {"number": 5, "title": "Speaker offline after router restart", "body": "wifi offline speaker router",
             "html_url": "https://x/5", "user": {"login": "starter"}},
        ]
        client.get_issue_comments.return_value = [
            _comment("starter", "thanks"), _comment("helper", "Reserve a fixed IP for the speaker in the router."),
        ]
        out = await find_sources(client, "Speaker offline", "after router restart wifi", [], tmp_path, "o/r")
        assert [s.kind for s in out] == ["thread"]
        assert "fixed IP" in out[0].text
        client.search_labelled_threads.assert_awaited_once()
        assert client.search_labelled_threads.call_args.args[0] == "verified-solution"

    @pytest.mark.asyncio
    async def test_docs_chunks_and_threshold(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "TROUBLESHOOTING.md").write_text(
            "# T\n\n## Speaker offline after router restart\nReserve a fixed IP for the speaker in the router wifi.\n\n"
            "## Unrelated\nColors and fonts of the web interface.\n", encoding="utf-8")
        client = AsyncMock()
        client.search_labelled_threads.return_value = []
        out = await find_sources(client, "Speaker offline", "after router restart wifi", [], tmp_path, "o/r")
        assert len(out) == 1
        assert out[0].url.endswith("docs/TROUBLESHOOTING.md#speaker-offline-after-router-restart")
        none = await find_sources(client, "Completely different", "nothing here at all", [], tmp_path, "o/r")
        assert none == []

    @pytest.mark.asyncio
    async def test_search_failure_is_not_fatal(self, tmp_path: Path) -> None:
        client = AsyncMock()
        client.search_labelled_threads.side_effect = RuntimeError("rate limit")
        assert await find_sources(client, "a b c", "d e f", [], tmp_path, "o/r") == []


class TestDryRunAndMarkers:
    @pytest.mark.asyncio
    async def test_writes_are_only_logged(self, capsys: pytest.CaptureFixture[str]) -> None:
        inner = AsyncMock()
        client = DryRunClient(inner)
        await client.post_comment(1, "hello")
        await client.add_labels(1, ["bug"])
        inner.post_comment.assert_not_called()
        inner.add_labels.assert_not_called()
        assert "dry_run" in capsys.readouterr().out
        await client.get_issue(1)
        inner.get_issue.assert_awaited_once()

    def test_finalize_adds_sources_footer_and_marker_once(self) -> None:
        src = [Source("docs", "T: Offline", "https://x/y", "t", 0.9)]
        out = finalize_comment("Answer.", src)
        assert "[T: Offline](https://x/y)" in out and out.endswith(ANSWER_MARKER)
        assert finalize_comment(out, src) == out
        assert finalize_comment("") == ""


class TestReviewFixes:
    @pytest.mark.asyncio
    async def test_generic_kb_tag_match_does_not_bypass_min_relevance(self, tmp_path: Path) -> None:
        from types import SimpleNamespace

        client = AsyncMock()
        client.search_labelled_threads.return_value = []
        kb = [SimpleNamespace(title="Bug report needed", filename="bug.md", content="Please send logs and steps.")]
        assert await find_sources(client, "Error", "an error happened somewhere", kb, tmp_path, "o/r") == []

    @pytest.mark.asyncio
    async def test_unreadable_thread_does_not_cost_the_answer(self, tmp_path: Path) -> None:
        client = AsyncMock()
        client.search_labelled_threads.return_value = [
            {"number": 5, "title": "Speaker offline after router restart", "body": "wifi offline speaker router",
             "html_url": "https://x/5", "user": {"login": "s"}},
        ]
        client.get_issue_comments.side_effect = RuntimeError("rate limit")
        assert await find_sources(client, "Speaker offline", "after router restart wifi", [], tmp_path, "o/r") == []

    @pytest.mark.asyncio
    async def test_discussion_ignores_other_bots_and_sees_the_marker(self) -> None:
        ev = _event(event_type="discussion", is_discussion=True, action="created")
        client = AsyncMock()
        client.get_discussion.return_value = {
            "closed": False, "labels": {"nodes": []},
            "comments": {"nodes": [{"author": {"login": "github-actions", "__typename": "Bot"}, "body": "ci"}]},
        }
        assert await recheck(ev, client, "oct-support") is None
        client.get_discussion.return_value["comments"]["nodes"][0]["body"] = "x " + ANSWER_MARKER
        assert "already answered" in (await recheck(ev, client, "oct-support") or "")


class TestSearchQuery:
    @pytest.mark.asyncio
    async def test_keywords_are_ored_and_capped(self) -> None:
        from unittest.mock import patch

        import httpx

        from github_client import GitHubClient

        client = GitHubClient("a", "b", "o", "r")
        resp = httpx.Response(200, json={"items": []}, request=httpx.Request("GET", "http://t"))
        with patch.object(client._search_client, "get", new_callable=AsyncMock, return_value=resp) as get:
            await client.search_labelled_threads("verified-solution", [f"word{i}" for i in range(9)])
        q = get.call_args.kwargs["params"]["q"]
        assert "word0 OR word1 OR word2 OR word3 OR word4" in q and "word5" not in q
