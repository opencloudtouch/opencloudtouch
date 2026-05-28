"""PR Reviewer — AI-powered code review via oct-support bot account.

Modes:
  review   — Analyze PR diff, submit review with inline comments
  approve  — Check if all review threads are resolved, auto-approve if yes

Environment variables:
  BOT_PAT          — oct-support PAT (needs repo, pull_request write)
  GITHUB_TOKEN     — Actions token for read operations
  OPENAI_API_KEY   — OpenAI API key for AI review
  PR_NUMBER        — Pull request number
  REPO_FULL_NAME   — owner/repo
  MODE             — "review" or "approve"
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from pathlib import Path

import httpx

# --- Retry config ---
MAX_RETRIES = 3
BASE_DELAY = 1.0
BACKOFF_FACTOR = 2.0
JITTER_MS = 500

API_BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

# Files to skip in review (generated, lock files, etc.)
SKIP_PATTERNS = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    ".local/",
    "node_modules/",
    "__pycache__/",
}

# Max diff size per file before truncation (tokens are expensive)
MAX_FILE_DIFF_CHARS = 8000
# Max total diff size sent to AI
MAX_TOTAL_DIFF_CHARS = 60000

BOT_USERNAME = os.environ.get("BOT_USERNAME", "oct-support")


async def _request_with_retry(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: object
) -> httpx.Response:
    """Execute request with exponential backoff on 403/429."""
    last_response: httpx.Response | None = None
    for attempt in range(MAX_RETRIES + 1):
        last_response = await getattr(client, method)(url, **kwargs)
        if last_response.status_code not in (403, 429):
            return last_response
        if attempt < MAX_RETRIES:
            delay = BASE_DELAY * (BACKOFF_FACTOR**attempt)
            jitter = random.uniform(-JITTER_MS / 1000, JITTER_MS / 1000)
            wait = max(0.1, delay + jitter)
            print(f"[WARN] {last_response.status_code} on {method.upper()} {url}, retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s")
            await asyncio.sleep(wait)
    assert last_response is not None
    last_response.raise_for_status()
    return last_response  # unreachable, but satisfies type checker


def _should_skip(filename: str) -> bool:
    """Check if a file should be excluded from review."""
    for pattern in SKIP_PATTERNS:
        if pattern in filename:
            return True
    return filename.endswith((".lock", ".sum", ".map"))


async def get_pr_details(client: httpx.AsyncClient, repo: str, pr_number: int) -> dict:
    """Fetch PR metadata."""
    resp = await _request_with_retry(client, "get", f"{API_BASE}/repos/{repo}/pulls/{pr_number}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


async def get_pr_diff(client: httpx.AsyncClient, repo: str, pr_number: int) -> str:
    """Fetch PR diff as unified diff text."""
    headers = {**HEADERS, "Accept": "application/vnd.github.v3.diff"}
    resp = await _request_with_retry(client, "get", f"{API_BASE}/repos/{repo}/pulls/{pr_number}", headers=headers)
    resp.raise_for_status()
    return resp.text


async def get_pr_files(client: httpx.AsyncClient, repo: str, pr_number: int) -> list[dict]:
    """Fetch list of changed files with patch data."""
    files = []
    page = 1
    while True:
        resp = await _request_with_retry(
            client, "get",
            f"{API_BASE}/repos/{repo}/pulls/{pr_number}/files",
            headers=HEADERS,
            params={"per_page": 100, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        files.extend(batch)
        page += 1
    return files


async def get_review_threads(client: httpx.AsyncClient, repo: str, pr_number: int) -> list[dict]:
    """Fetch all review comments on a PR, grouped by thread.

    Returns list of threads with their resolution status.
    Uses the GraphQL API for thread resolution status.
    """
    owner, name = repo.split("/")
    query = """
    query($owner: String!, $name: String!, $pr: Int!) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              comments(first: 1) {
                nodes {
                  author { login }
                  body
                }
              }
            }
          }
        }
      }
    }
    """
    resp = await _request_with_retry(
        client, "post",
        f"{API_BASE}/graphql",
        headers=HEADERS,
        json={"query": query, "variables": {"owner": owner, "name": name, "pr": pr_number}},
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        print(f"[WARN] GraphQL errors: {data['errors']}", file=sys.stderr)
        return []

    threads_data = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    return threads_data


async def get_existing_reviews(client: httpx.AsyncClient, repo: str, pr_number: int) -> list[dict]:
    """Get all reviews on a PR."""
    resp = await _request_with_retry(
        client, "get",
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


def build_review_prompt(pr_details: dict, files: list[dict]) -> str:
    """Build the AI prompt for reviewing a PR."""
    title = pr_details["title"]
    body = pr_details.get("body") or "(no description)"
    base = pr_details["base"]["ref"]
    head = pr_details["head"]["ref"]

    # Build file diffs, respecting size limits
    file_sections = []
    total_chars = 0
    for f in files:
        filename = f["filename"]
        if _should_skip(filename):
            continue
        status = f["status"]  # added, removed, modified, renamed
        patch = f.get("patch", "")

        if total_chars + len(patch) > MAX_TOTAL_DIFF_CHARS:
            file_sections.append(f"\n### {filename} ({status})\n[TRUNCATED — diff too large]")
            continue

        if len(patch) > MAX_FILE_DIFF_CHARS:
            patch = patch[:MAX_FILE_DIFF_CHARS] + "\n... [truncated]"

        file_sections.append(f"\n### {filename} ({status})\n```diff\n{patch}\n```")
        total_chars += len(patch)

    files_text = "\n".join(file_sections) if file_sections else "(no reviewable file changes)"

    return f"""You are a senior code reviewer for the OpenCloudTouch project (Python backend + React/TypeScript frontend).
Review this pull request carefully and provide actionable feedback.

## PR Details
- **Title:** {title}
- **Branch:** {head} → {base}
- **Description:** {body}

## Changed Files
{files_text}

## Review Guidelines
1. Focus on: bugs, security issues, logic errors, missing error handling, test gaps
2. Consider: naming, readability, Clean Code principles, SOLID
3. Check: type safety, edge cases, resource cleanup, error messages
4. Note: imports, unused variables, potential race conditions
5. Be constructive — suggest specific fixes, not just "this is wrong"
6. If the code looks good, say so. Don't invent problems.
7. For each issue found, specify the exact file and line number from the diff

## Output Format
Respond with a JSON object:
{{
  "summary": "Brief overall assessment (2-3 sentences)",
  "verdict": "approve" | "request_changes" | "comment",
  "comments": [
    {{
      "path": "relative/file/path",
      "line": <line number in the new version of the file>,
      "side": "RIGHT",
      "body": "Your review comment with suggestion"
    }}
  ]
}}

If no issues found, use verdict "approve" with empty comments array.
Only use "request_changes" for actual bugs, security issues, or critical problems.
Use "comment" for style suggestions or minor improvements.
"""


async def run_ai_review(prompt: str) -> dict:
    """Send the review prompt to OpenAI and parse the response."""
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a precise code reviewer. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    return json.loads(content)


async def submit_review(
    client: httpx.AsyncClient,
    repo: str,
    pr_number: int,
    commit_sha: str,
    review_result: dict,
) -> None:
    """Submit the AI review as a GitHub PR review from oct-support."""
    event_map = {
        "approve": "APPROVE",
        "request_changes": "REQUEST_CHANGES",
        "comment": "COMMENT",
    }
    verdict = review_result.get("verdict", "comment")
    event = event_map.get(verdict, "COMMENT")

    # Don't auto-approve on first review — always provide feedback first
    if event == "APPROVE" and not review_result.get("comments"):
        event = "APPROVE"
        body = f"✅ **AI Review — No issues found**\n\n{review_result.get('summary', 'Code looks good.')}"
    else:
        if event == "APPROVE":
            # Has comments but still approves
            body = f"✅ **AI Review — Approved with comments**\n\n{review_result.get('summary', '')}"
        else:
            body = f"🔍 **AI Review — Changes requested**\n\n{review_result.get('summary', '')}"

    # Build review comments
    comments = []
    for c in review_result.get("comments", []):
        if not c.get("path") or not c.get("line"):
            continue
        comments.append({
            "path": c["path"],
            "line": c["line"],
            "side": c.get("side", "RIGHT"),
            "body": c["body"],
        })

    payload: dict = {"body": body, "event": event, "commit_id": commit_sha}
    if comments:
        payload["comments"] = comments

    resp = await client.post(
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=HEADERS,
        json=payload,
    )

    if resp.status_code == 422 and comments:
        # Retry without inline comments if positions are invalid
        print("[WARN] Inline comments failed, submitting review without them", file=sys.stderr)
        fallback_body = body
        if comments:
            fallback_body += "\n\n---\n**Inline comments (could not attach to diff):**\n"
            for c in comments:
                fallback_body += f"\n**`{c['path']}` line {c['line']}:** {c['body']}\n"

        payload = {"body": fallback_body, "event": event, "commit_id": commit_sha}
        resp = await client.post(
            f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
            headers=HEADERS,
            json=payload,
        )

    resp.raise_for_status()
    print(f"[OK] Review submitted: {event} with {len(comments)} inline comments")


async def check_and_approve(client: httpx.AsyncClient, repo: str, pr_number: int) -> None:
    """Check if all oct-support review threads are resolved. If yes, approve."""
    # Get current review threads
    threads = await get_review_threads(client, repo, pr_number)

    # Filter to threads started by oct-support
    bot_threads = [
        t for t in threads
        if t.get("comments", {}).get("nodes")
        and t["comments"]["nodes"][0].get("author", {}).get("login") == BOT_USERNAME
    ]

    if not bot_threads:
        print("[INFO] No review threads from oct-support found. Nothing to approve.")
        return

    unresolved = [t for t in bot_threads if not t.get("isResolved")]

    if unresolved:
        print(f"[INFO] {len(unresolved)}/{len(bot_threads)} threads still unresolved. Not approving yet.")
        return

    # All threads resolved — check if there's already an approval
    reviews = await get_existing_reviews(client, repo, pr_number)
    latest_bot_review = None
    for r in reversed(reviews):
        if r.get("user", {}).get("login") == BOT_USERNAME:
            latest_bot_review = r
            break

    if latest_bot_review and latest_bot_review.get("state") == "APPROVED":
        print("[INFO] PR already approved by oct-support. Skipping.")
        return

    # Get latest commit SHA
    pr_details = await get_pr_details(client, repo, pr_number)
    commit_sha = pr_details["head"]["sha"]

    # Submit approval
    payload = {
        "body": "✅ **All review threads resolved — auto-approved.**\n\nAll issues from the previous review have been addressed.",
        "event": "APPROVE",
        "commit_id": commit_sha,
    }
    resp = await client.post(
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=HEADERS,
        json=payload,
    )
    resp.raise_for_status()
    print(f"[OK] PR #{pr_number} approved by oct-support — all {len(bot_threads)} threads resolved.")


async def run() -> int:
    """Main entry point."""
    mode = os.environ.get("MODE", "review")
    repo = os.environ.get("REPO_FULL_NAME", "")
    pr_number_str = os.environ.get("PR_NUMBER", "")
    bot_pat = os.environ.get("BOT_PAT", "")

    if not repo or not pr_number_str or not bot_pat:
        print("[ERROR] Missing required env vars: REPO_FULL_NAME, PR_NUMBER, BOT_PAT", file=sys.stderr)
        return 1

    pr_number = int(pr_number_str)

    async with httpx.AsyncClient(
        headers={**HEADERS, "Authorization": f"Bearer {bot_pat}"},
        timeout=60.0,
    ) as client:
        if mode == "review":
            print(f"[INFO] Reviewing PR #{pr_number} in {repo}...")
            pr_details = await get_pr_details(client, repo, pr_number)
            files = await get_pr_files(client, repo, pr_number)

            reviewable = [f for f in files if not _should_skip(f["filename"])]
            if not reviewable:
                print("[INFO] No reviewable files changed. Skipping review.")
                return 0

            prompt = build_review_prompt(pr_details, files)
            review_result = await run_ai_review(prompt)
            commit_sha = pr_details["head"]["sha"]
            await submit_review(client, repo, pr_number, commit_sha, review_result)

        elif mode == "approve":
            print(f"[INFO] Checking approval status for PR #{pr_number} in {repo}...")
            await check_and_approve(client, repo, pr_number)

        else:
            print(f"[ERROR] Unknown mode: {mode}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
