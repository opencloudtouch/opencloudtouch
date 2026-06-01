"""Pattern & Quality Scan for KB workflow (deterministic, YAML output).

Scans open issues/discussions for:
- Pattern matches (problem, how, workaround, fixed, thanks, etc.)
- Stale detection (>7d no activity)
- KB coverage (topic/tag mapping)
- Response quality (feedback signals)

Outputs YAML reports for coverage and quality.
"""

import os
import sys
import re
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from github_client import GitHubClient
from knowledge_base import KnowledgeBase

PATTERNS = [
    r"\\bhow\\b", r"\\bwhy\\b", r"doesn['’]t work", r"problem", r"workaround", r"fixed", r"solved", r"thanks?",
    r"great", r"perfect", r"confirmed", r"appreciate"
]
POSITIVE_FEEDBACK = [r"thanks?", r"works", r"solved", r"fixed", r"perfect", r"that did it", r"confirmed", r"great"]
NEGATIVE_FEEDBACK = [r"doesn['’]t work", r"still broken", r"no effect", r"gave up", r"not fixed"]

STALE_DAYS = 7

async def scan_open_issues(github_client: GitHubClient, kb: KnowledgeBase):
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    open_issues = await github_client.get_open_issues_since(since)
    all_answers = kb.get_all_answers()
    all_tags = set(tag.lower() for a in all_answers for tag in a.tags)
    coverage_map = {}
    quality = {"helpful": 0, "solved": 0, "didn’t_work": 0, "no_response": 0, "details": []}
    threads = []
    now = datetime.now(timezone.utc)
    for issue in open_issues:
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        last_activity = issue.get("updated_at", issue.get("created_at", ""))
        last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
        stale = (now - last_dt).days > STALE_DAYS
        text = (title + " " + body).lower()
        patterns = [p for p in PATTERNS if re.search(p, text)]
        words = set(text.split())
        tag_overlap = words & all_tags
        kb_match = bool(tag_overlap)
        feedback = None
        score = 0
        # Simulate feedback scan (real impl: scan comments)
        for pf in POSITIVE_FEEDBACK:
            if re.search(pf, text):
                feedback = pf
                score = 2 if pf in ["thanks", "solved", "fixed"] else 1
                quality["solved" if score == 2 else "helpful"] += 1
                break
        for nf in NEGATIVE_FEEDBACK:
            if re.search(nf, text):
                feedback = nf
                score = -1
                quality["didn’t_work"] += 1
                break
        if not feedback and stale:
            quality["no_response"] += 1
        threads.append({
            "id": issue.get("number"),
            "title": title,
            "last_activity": last_activity,
            "patterns": patterns,
            "kb_match": kb_match,
            "duplicate_of": None,  # TODO: Dupe detection
            "stale": stale,
            "bot_response": {"score": score, "feedback": feedback}
        })
    # Coverage map
    for a in all_answers:
        topic = a.title or a.tags[0] if a.tags else a.filename
        covered = any(topic.lower() in (t["title"]+" "+t["title"]).lower() for t in threads if t["kb_match"])
        open_threads = [t["id"] for t in threads if topic.lower() in (t["title"]+" "+t["title"]).lower()]
        coverage_map[topic] = {"covered_by_kb": covered, "open_threads": open_threads}
    # Write YAML outputs
    Path(".local/agent-work/knowledge-kai/scans/").mkdir(parents=True, exist_ok=True)
    with open(".local/agent-work/knowledge-kai/scans/pattern_quality_threads.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"threads": threads}, f, allow_unicode=True)
    with open(".local/agent-work/knowledge-kai/scans/pattern_quality_coverage.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"coverage": coverage_map}, f, allow_unicode=True)
    with open(".local/agent-work/knowledge-kai/scans/pattern_quality_quality.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"quality": quality}, f, allow_unicode=True)
    print("Pattern & quality scan complete. YAML reports written.")

if __name__ == "__main__":
    import asyncio
    github_token = os.environ.get("GITHUB_TOKEN", "")
    bot_pat = os.environ.get("BOT_PAT", "")
    repo_owner = os.environ.get("REPO_OWNER", "opencloudtouch")
    repo_name = os.environ.get("REPO_NAME", "opencloudtouch")
    if not github_token or not bot_pat:
        print("[ERROR] GITHUB_TOKEN and BOT_PAT required", file=sys.stderr)
        sys.exit(1)
    client = GitHubClient(
        bot_pat=bot_pat,
        github_token=github_token,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
    kb_dir = str(Path(__file__).parent / "approved_answers")
    kb = KnowledgeBase(kb_dir)
    asyncio.run(scan_open_issues(client, kb))
    asyncio.run(client.close())
