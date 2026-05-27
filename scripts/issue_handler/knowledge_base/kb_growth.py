"""Weekly KB growth scan — identifies closed support issues for KB expansion (T034).

Scans closed support issues since last run, matches against existing KB tags,
and produces a digest markdown for the weekly KB growth issue.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_client import GitHubClient
from knowledge_base import KnowledgeBase


async def scan_closed_issues(
    github_client: GitHubClient,
    kb: KnowledgeBase,
    since_days: int = 7,
) -> dict:
    """Scan closed issues for KB growth candidates.

    Returns dict with scan results and digest markdown.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()

    # Fetch closed support issues
    closed_issues = await github_client.get_closed_issues_since(since, labels=["support"])

    # Filter out already-scanned issues (those with kb-scanned label)
    unscanned = [
        issue for issue in closed_issues
        if not any(
            label.get("name") == "kb-scanned" if isinstance(label, dict) else label == "kb-scanned"
            for label in issue.get("labels", [])
        )
    ]

    # Match against existing KB tags
    all_answers = kb.get_all_answers()
    all_tags = set()
    for answer in all_answers:
        all_tags.update(tag.lower() for tag in answer.tags)

    candidates = []
    covered = []

    for issue in unscanned:
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        words = set((title + " " + body).lower().split())

        # Check if issue topic is already covered by existing KB
        tag_overlap = words & all_tags
        if tag_overlap and len(tag_overlap) >= 2:
            covered.append(issue)
        else:
            candidates.append(issue)

    return {
        "total_scanned": len(closed_issues),
        "support_count": len(unscanned),
        "covered_count": len(covered),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "covered": covered,
    }


def generate_digest(scan_result: dict) -> str:
    """Generate digest markdown from scan results."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"## 📚 KB Growth Digest — Week of {date_str}",
        "",
        f"**Scanned**: {scan_result['total_scanned']} closed issues since last run",
        f"**Support issues**: {scan_result['support_count']}",
        f"**Already covered by KB**: {scan_result['covered_count']}",
        f"**🆕 KB candidates**: {scan_result['candidate_count']}",
    ]

    candidates = scan_result.get("candidates", [])
    if candidates:
        lines.append("")
        lines.append("### Candidates for new KB articles")
        lines.append("")
        for i, issue in enumerate(candidates, 1):
            number = issue.get("number", "?")
            title = issue.get("title", "Unknown")
            lines.append(f"#### {i}. #{number} — \"{title}\"")
            lines.append("")
    else:
        lines.append("")
        lines.append("No new KB candidates this week. 🎉")

    return "\n".join(lines)


async def run_kb_growth(
    github_client: GitHubClient,
    kb: KnowledgeBase,
    since_days: int = 7,
) -> str:
    """Run full KB growth scan and return digest markdown."""
    scan_result = await scan_closed_issues(github_client, kb, since_days)
    digest = generate_digest(scan_result)

    # Apply kb-scanned label to all processed issues
    for issue in scan_result.get("candidates", []) + scan_result.get("covered", []):
        issue_number = issue.get("number")
        if issue_number:
            try:
                await github_client.add_labels(issue_number, ["kb-scanned"])
            except Exception as e:
                logger.warning("Failed to apply kb-scanned to #%s: %s", issue_number, e)

    return digest


async def main() -> int:
    """Entry point for KB growth scan."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    bot_pat = os.environ.get("BOT_PAT", "")
    repo_owner = os.environ.get("REPO_OWNER", "opencloudtouch")
    repo_name = os.environ.get("REPO_NAME", "opencloudtouch")

    if not github_token or not bot_pat:
        print("[ERROR] GITHUB_TOKEN and BOT_PAT required", file=sys.stderr)
        return 1

    client = GitHubClient(
        bot_pat=bot_pat,
        github_token=github_token,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )

    kb_dir = str(Path(__file__).parent / "approved_answers")
    kb = KnowledgeBase(kb_dir)

    try:
        digest = await run_kb_growth(client, kb)
        print(digest)

        # Write to GitHub Step Summary if available
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write(digest + "\n")

        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
