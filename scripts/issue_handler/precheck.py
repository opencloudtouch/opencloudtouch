"""Checks around the delayed answer: which events never answer, and what changed during the wait."""

from __future__ import annotations

import os
import random
from typing import Any

from bot_markers import ANSWER_MARKER
from models import WebhookEvent

SKIP_LABELS = {"spec", "needs-human"}


def early_skip_reason(event: WebhookEvent) -> str | None:
    """Events that never produce a first answer."""
    if event.action == "edited":
        return "edited events never trigger an answer"
    if event.event_type == "issue_comment":
        return "comments never trigger a first answer"
    return None


def delay_seconds(settings: dict[str, Any], rng: Any = random) -> float:
    """Random wait before answering; env OCT_BOT_DELAY_MIN/MAX (seconds) override rules.yml."""
    low = float(os.environ.get("OCT_BOT_DELAY_MIN", settings.get("answer_delay_min_seconds", 300)))
    high = float(os.environ.get("OCT_BOT_DELAY_MAX", settings.get("answer_delay_max_seconds", 600)))
    return rng.uniform(low, max(low, high))


def _foreign(commenters: list[tuple[str, str]], author: str, bot: str) -> bool:
    """True if someone other than the thread starter and the bot (and not any bot) commented."""
    return any(login not in (author, bot) and kind != "Bot" for login, kind in commenters)


async def recheck(event: WebhookEvent, client: Any, bot_username: str) -> str | None:
    """Re-read the thread after the wait. Returns a skip reason or None when the bot may answer."""
    if event.issue_number is None:
        return "no thread number"
    if event.is_discussion:
        d = await client.get_discussion(event.issue_number)
        if not d:
            return "discussion is gone"
        if d.get("closed"):
            return "discussion is closed"
        labels = {n["name"] for n in (d.get("labels") or {}).get("nodes", [])}
        nodes = d["comments"]["nodes"]
        comments = [((c.get("author") or {}).get("login", ""), (c.get("author") or {}).get("__typename", "User")) for c in nodes]
        if any(login == bot_username for login, _ in comments) or any(_has_marker(c.get("body") or "") for c in nodes):
            return "bot already answered"
    else:
        issue = await client.get_issue(event.issue_number)
        if not issue or issue.get("state") != "open":
            return "issue is closed or gone"
        labels = {lbl["name"] for lbl in issue.get("labels", [])}
        raw = await client.get_issue_comments(event.issue_number)
        comments = [((c.get("user") or {}).get("login", ""), (c.get("user") or {}).get("type", "User")) for c in raw]
        if any(login == bot_username for login, _ in comments):
            return "bot already answered"
        if any(_has_marker(c.get("body") or "") for c in raw):
            return "bot already answered"
    if labels & SKIP_LABELS:
        return f"thread has label {sorted(labels & SKIP_LABELS)[0]}"
    if _foreign(comments, event.author_login, bot_username):
        return "a human already replied"
    return None


def _has_marker(text: str) -> bool:
    return ANSWER_MARKER in text
