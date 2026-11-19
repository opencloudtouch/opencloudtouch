"""Daily job: label unanswered threads and post the one follow-up (python followup_main.py)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from ai_context import make_ai_context
from cost_tracker import report_cost
from dry_run import DryRunClient
from followup import DEFAULTS, SKIP_LABELS, Thread, _ts, discussion_to_thread, issue_to_thread, plan
from github_client import GitHubClient
from main import _load_settings


async def collect_threads(client: Any, now: datetime, settings: dict[str, Any]) -> list[Thread]:
    max_age = settings["followup_max_age_days"]
    threads: list[Thread] = []
    for issue in await client.list_open_issues():
        labels = {lbl["name"] for lbl in issue.get("labels", [])}
        if labels & SKIP_LABELS or (now - _ts(issue["created_at"])).days > max_age:
            continue
        comments = await client.get_issue_comments(issue["number"])
        threads.append(issue_to_thread(issue, comments, ""))
    threads += [discussion_to_thread(d) for d in await client.list_open_discussions()]
    return threads


async def run_followups(client: Any, ai: dict[str, Any], settings: dict[str, Any], bot: str, now: datetime) -> list[dict[str, Any]]:
    s = {**DEFAULTS, **settings}
    done: list[dict[str, Any]] = []
    posted = 0
    for thread in await collect_threads(client, now, s):
        # Past the per-run limit no AI call is spent on a follow-up that would only be deferred
        decision = await plan(thread, bot, now, s, ai, build_body=posted < s["followup_max_per_run"])
        if decision is None:
            continue
        entry = {"thread": thread.number, "kind": thread.kind, "case": decision["case"], "label": decision["label"], "followup": bool(decision["body"])}
        if decision["label"]:
            await client.add_labels(thread.number, ["unanswered"])
        if decision["body"] and posted < s["followup_max_per_run"]:
            if thread.kind == "issue":
                await client.post_comment(thread.number, decision["body"], allow_repeat=True)
            else:
                await client.post_discussion_comment(thread.node_id, decision["body"])
            posted += 1
        elif decision["due"]:
            entry["followup"] = False
            entry["deferred"] = "per-run limit"
        done.append(entry)
    return done


async def main() -> int:
    token, pat = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("BOT_PAT", "")
    if not token or not pat:
        print("[ERROR] GITHUB_TOKEN and BOT_PAT required", file=sys.stderr)
        return 1
    owner, repo = os.environ.get("REPO_OWNER", "opencloudtouch"), os.environ.get("REPO_NAME", "opencloudtouch")
    settings = _load_settings()
    client: Any = GitHubClient(bot_pat=pat, github_token=token, repo_owner=owner, repo_name=repo)
    if os.environ.get("OCT_BOT_DRY_RUN", "true").lower() != "false":
        client = DryRunClient(client)
    ai: dict[str, Any] = {}
    try:
        ai = await make_ai_context(settings)
        result = await run_followups(client, ai, settings, settings.get("bot_username", "oct-support"), datetime.now(timezone.utc))
        print(json.dumps({"followups": result}))
        return 0
    finally:
        report_cost(ai.get("cost_tracker"))
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
