"""PR Reviewer — AI-powered code review via oct-support bot account.

Modes:
  review   — Analyze PR diff, submit review with inline comments
  approve  — Check if all review threads are resolved, auto-approve if yes

Environment variables:
  BOT_PAT          — oct-support PAT (needs repo, pull_request write)
  GITHUB_TOKEN     — Actions token (also used for GitHub Models free tier)
  OPENAI_API_KEY   — OpenAI API key (fallback only)
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

# --- Retry config ---
MAX_RETRIES = 3
BASE_DELAY = 1.0
BACKOFF_FACTOR = 2.0
JITTER_MS = 500

API_BASE = "https://api.github.com"
GITHUB_MODELS_BASE = "https://models.inference.ai.azure.com"
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

# Cost tracking — GPT-4o pricing (fallback only, primary is free GitHub Models)
# Source: https://platform.openai.com/settings/organization/limits
# Our tier limits for gpt-4o (OpenAI fallback):
#   - 30,000 TPM (tokens per minute)
#   - 500 RPM (requests per minute)
#   - 90,000 TPD (tokens per day)
# GitHub Models free tier (primary): 150 req/day, rate limits vary by model
INPUT_COST_PER_TOKEN = 2.50 / 1_000_000
OUTPUT_COST_PER_TOKEN = 10.00 / 1_000_000
MONTHLY_BUDGET_USD = 1.00

# Rate limiting — cooldown per PR (seconds)
REVIEW_COOLDOWN_SECONDS = 300  # 5 min between reviews on same PR

# CI polling — wait for CI to complete before reviewing
CI_POLL_INTERVAL_SECONDS = 30
CI_POLL_MAX_WAIT_SECONDS = 1200  # 20 min max wait (CI avg ~10 min, max ~11 min + growth buffer)

BOT_USERNAME = os.environ.get("BOT_USERNAME", "oct-support")


# =============================================================================
# Cost Tracker (adapted from issue_handler/cost_tracker.py)
# =============================================================================

@dataclass
class CostRecord:
    """Tracks monthly AI cost."""

    month: str
    total_cost_usd: float = 0.0
    call_count: int = 0
    last_updated: str = ""


class CostTracker:
    """Track monthly AI API costs with budget enforcement."""

    def __init__(self, cost_file: Path, budget_usd: float = MONTHLY_BUDGET_USD) -> None:
        self._cost_file = cost_file
        self._budget_usd = budget_usd
        self._month: str = datetime.now(timezone.utc).strftime("%Y-%m")
        self._record = CostRecord(month=self._month)
        self._load()

    @property
    def total_cost_usd(self) -> float:
        return self._record.total_cost_usd

    @property
    def call_count(self) -> int:
        return self._record.call_count

    def _load(self) -> None:
        if not self._cost_file.exists():
            return
        try:
            data = json.loads(self._cost_file.read_text())
            if data.get("month") == self._month:
                self._record.total_cost_usd = data.get("total_cost_usd", 0.0)
                self._record.call_count = data.get("call_count", 0)
                self._record.last_updated = data.get("last_updated", "")
        except (json.JSONDecodeError, KeyError):
            # Ignore malformed or unexpected cost-file contents and keep defaults.
            return

    def save(self) -> None:
        self._cost_file.parent.mkdir(parents=True, exist_ok=True)
        self._record.last_updated = datetime.now(timezone.utc).isoformat()
        data = {
            "month": self._record.month,
            "total_cost_usd": self._record.total_cost_usd,
            "call_count": self._record.call_count,
            "last_updated": self._record.last_updated,
        }
        self._cost_file.write_text(json.dumps(data, indent=2))

    def record_call(self, input_tokens: int, output_tokens: int) -> None:
        cost = (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)
        self._record.total_cost_usd += cost
        self._record.call_count += 1

    def is_budget_exceeded(self) -> bool:
        return self._record.total_cost_usd >= self._budget_usd


# =============================================================================
# Rate Limiter
# =============================================================================

class ReviewRateLimiter:
    """Enforce cooldown between reviews on the same PR."""

    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file
        self._state: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._state_file.exists():
            return
        try:
            self._state = json.loads(self._state_file.read_text())
        except (json.JSONDecodeError, KeyError) as exc:
            # Fail open: ignore invalid persisted state and continue with empty state.
            print(f"[WARN] Failed to load review rate limiter state from {self._state_file}: {exc}")
            self._state = {}

    def save(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(self._state, indent=2))

    def check_and_record(self, pr_key: str) -> bool:
        """Return True if review is allowed, False if rate-limited."""
        now = datetime.now(timezone.utc)
        last_str = self._state.get(pr_key)
        if last_str:
            try:
                last = datetime.fromisoformat(last_str)
                elapsed = (now - last).total_seconds()
                if elapsed < REVIEW_COOLDOWN_SECONDS:
                    print(
                        f"[RATE-LIMIT] PR {pr_key} was reviewed {elapsed:.0f}s ago "
                        f"(cooldown: {REVIEW_COOLDOWN_SECONDS}s). Skipping."
                    )
                    return False
            except ValueError:
                print(
                    f"[WARN] Invalid stored review timestamp for PR {pr_key}: "
                    f"{last_str!r}. Treating as no previous review."
                )
        self._state[pr_key] = now.isoformat()
        return True


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


def _parse_diff_lines(patch: str) -> set[int]:
    """Extract valid NEW-side line numbers from a unified diff patch.

    GitHub only allows review comments on lines visible in the diff.
    Returns the set of line numbers (in the new file) that appear in diff hunks.
    """
    import re
    valid_lines: set[int] = set()
    current_line = 0
    for raw_line in patch.split("\n"):
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw_line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue
        if current_line == 0:
            continue
        if raw_line.startswith("-"):
            # Deleted line — not in new file, skip
            continue
        if raw_line.startswith("+") or not raw_line.startswith("\\"):
            # Added or context line — valid in new file
            valid_lines.add(current_line)
            current_line += 1
    return valid_lines


def _build_valid_lines_map(files: list[dict]) -> dict[str, set[int]]:
    """Build a map of filename → set of valid diff line numbers."""
    result: dict[str, set[int]] = {}
    for f in files:
        patch = f.get("patch", "")
        if patch:
            result[f["filename"]] = _parse_diff_lines(patch)
    return result


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


async def wait_for_ci(client: httpx.AsyncClient, repo: str, commit_sha: str) -> tuple[bool, list[str]]:
    """Wait for CI checks to complete, then return final status.

    Polls every CI_POLL_INTERVAL_SECONDS until all checks are done or timeout.
    Returns (all_passed, failure_details).
    """
    import time
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        all_passed, failures = await get_ci_status(client, repo, commit_sha)

        # Check if any are still pending/in_progress
        still_running = [f for f in failures if "still " in f]
        if not still_running:
            # All checks completed (or no checks at all)
            return all_passed, failures

        if elapsed >= CI_POLL_MAX_WAIT_SECONDS:
            print(f"[WARN] CI polling timeout after {elapsed:.0f}s. Proceeding with current status.")
            return all_passed, failures

        print(f"[INFO] CI still running ({len(still_running)} pending), waiting {CI_POLL_INTERVAL_SECONDS}s... ({elapsed:.0f}s/{CI_POLL_MAX_WAIT_SECONDS}s)")
        await asyncio.sleep(CI_POLL_INTERVAL_SECONDS)


async def get_ci_status(client: httpx.AsyncClient, repo: str, commit_sha: str) -> tuple[bool, list[str]]:
    """Check if all CI checks pass for a commit.

    Returns (all_passed, failure_details) where failure_details lists failing check names.
    Checks both Check Runs (GitHub Actions) and Commit Status (legacy status API).
    """
    failures: list[str] = []

    # 1. Check Runs (GitHub Actions, CodeQL, etc.)
    resp = await _request_with_retry(
        client, "get",
        f"{API_BASE}/repos/{repo}/commits/{commit_sha}/check-runs",
        headers=HEADERS,
        params={"per_page": 100},
    )
    resp.raise_for_status()
    check_runs = resp.json().get("check_runs", [])

    for cr in check_runs:
        name = cr.get("name", "unknown")
        status = cr.get("status")  # queued, in_progress, completed
        conclusion = cr.get("conclusion")  # success, failure, neutral, cancelled, skipped, timed_out, action_required

        # Skip our own PR Review checks to avoid circular dependency
        # Job names: "PR Review", "Approve Check", "Comment Trigger"
        # Workflow may prefix with "PR Review (oct-support) / "
        # Also filter legacy name "AI Review" from old runs still attached to commits
        if any(skip in name for skip in ("PR Review", "Approve Check", "Comment Trigger", "AI Review")) \
                or "pr-review" in name.lower():
            continue

        if status != "completed":
            failures.append(f"{name} (still {status})")
        elif conclusion not in ("success", "neutral", "skipped"):
            failures.append(f"{name} ({conclusion})")

    # 2. Commit Status (legacy — some integrations use this)
    resp = await _request_with_retry(
        client, "get",
        f"{API_BASE}/repos/{repo}/commits/{commit_sha}/status",
        headers=HEADERS,
    )
    resp.raise_for_status()
    status_data = resp.json()

    for s in status_data.get("statuses", []):
        context = s.get("context", "unknown")
        state = s.get("state")  # pending, success, error, failure
        if state not in ("success", "pending"):
            failures.append(f"{context} ({state})")

    all_passed = len(failures) == 0
    return all_passed, failures


async def get_existing_reviews(client: httpx.AsyncClient, repo: str, pr_number: int) -> list[dict]:
    """Get all reviews on a PR."""
    resp = await _request_with_retry(
        client, "get",
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


async def has_bot_reviewed_commit(client: httpx.AsyncClient, repo: str, pr_number: int, commit_sha: str) -> bool:
    """Check if oct-support already reviewed this specific commit."""
    reviews = await get_existing_reviews(client, repo, pr_number)
    for r in reviews:
        if (r.get("user", {}).get("login") == BOT_USERNAME
                and r.get("commit_id") == commit_sha
                and r.get("state") in ("COMMENTED", "CHANGES_REQUESTED", "APPROVED")):
            return True
    return False


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

    return f"""You are a senior staff engineer reviewing code for the OpenCloudTouch project.

## Project Context
OpenCloudTouch is a self-hosted alternative cloud server for Bose SoundTouch speakers.
- **Backend**: Python 3.11+, FastAPI, async/await, Clean Architecture (routes → service → repository/adapter)
- **Frontend**: React 19, TypeScript strict mode, TanStack React Query, Vite, functional components only
- **Testing**: pytest (backend), vitest + Cypress (frontend). Coverage ≥80% enforced.
- **Patterns**: Repository pattern for data access, adapter pattern for external systems, dependency injection via constructors
- **Security**: No secrets in code, defusedxml for XML parsing, input validation at API boundaries

## PR Details
- **Title:** {title}
- **Branch:** {head} → {base}
- **Description:** {body}

## Changed Files
{files_text}

## What to Review (HIGH VALUE — focus here)
1. **Bugs**: Logic errors, off-by-one, null/undefined access, wrong variable, inverted conditions, missing await
2. **Security**: SQL injection, path traversal, unvalidated user input, hardcoded secrets, XML injection, SSRF
3. **Data integrity**: Missing transactions, race conditions, partial writes without rollback, lost updates
4. **Error handling**: Swallowed exceptions, missing try/catch around I/O, unclear error messages for users
5. **API contract**: Response shape mismatches, missing fields, wrong HTTP status codes, breaking changes
6. **Resource leaks**: Unclosed connections/files/streams, missing cleanup in finally/context managers
7. **Type safety**: Wrong types passed across boundaries, unsafe casts, missing None checks

## What NOT to Review (LOW VALUE — skip entirely)
- Naming conventions, variable naming style
- Missing comments or docstrings
- Import ordering
- Code formatting (handled by Black/Prettier)
- Test naming patterns
- "Consider extracting a helper" suggestions
- Any suggestion starting with "consider" or "you might want to"

## Review Philosophy
- If the code works correctly and is safe, **approve it**. Don't manufacture issues.
- Every comment must identify a **concrete problem** with a **specific fix**.
- Prefer showing the corrected code over describing what to change.
- A great review catches the bug the author missed, not the style the author chose.

## Output Format
Respond with a JSON object:
{{
  "summary": "Brief overall assessment (2-3 sentences). What does this PR do? Is it safe to merge?",
  "verdict": "approve" | "request_changes" | "comment",
  "comments": [
    {{
      "path": "relative/file/path",
      "line": <line number from the diff — must be a + line or context line>,
      "side": "RIGHT",
      "body": "**Bug/Security/Issue type**: Clear description of the problem.\\n\\nSuggested fix:\\n```python\\n# corrected code here\\n```"
    }}
  ]
}}

## Verdict Rules
- **"approve"**: No real issues found. This should be the most common verdict for well-written code.
- **"comment"**: Minor non-blocking observations (1-2 items). Things the author should know but that don't block merge.
- **"request_changes"**: ONLY for actual bugs, security vulnerabilities, data loss risks. Must be clearly justified.

IMPORTANT: Line numbers MUST correspond to lines visible in the diff (lines starting with + or context lines).
If no real issues found, use verdict "approve" with an empty comments array.
"""


async def run_ai_review(prompt: str, cost_tracker: CostTracker) -> dict:
    """Send the review prompt to AI. GitHub Models primary, OpenAI fallback."""
    from openai import AsyncOpenAI

    github_token = os.environ.get("GITHUB_TOKEN", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")

    messages = [
        {"role": "system", "content": (
            "You are a senior staff engineer performing code reviews. "
            "You think carefully about correctness, security, and edge cases. "
            "You never comment on style or formatting — only real issues that could cause bugs or security problems. "
            "When you find no issues, you approve without hesitation. "
            "Respond only with valid JSON matching the requested schema."
        )},
        {"role": "user", "content": prompt},
    ]
    kwargs = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }

    # Try GitHub Models first (free tier, 150 req/day)
    if github_token:
        try:
            client = AsyncOpenAI(
                base_url=GITHUB_MODELS_BASE,
                api_key=github_token,
            )
            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or "{}"
            print("[OK] Review generated via GitHub Models (free tier)")
            return json.loads(content)
        except Exception as e:
            print(f"[WARN] GitHub Models failed: {e}, falling back to OpenAI", file=sys.stderr)

    # Fallback: OpenAI (with cost tracking + budget check)
    if not openai_api_key:
        print("[ERROR] No AI provider available (GitHub Models failed, OPENAI_API_KEY not set)", file=sys.stderr)
        sys.exit(1)

    if cost_tracker.is_budget_exceeded():
        print(
            f"[BUDGET] Monthly budget exceeded (${cost_tracker.total_cost_usd:.4f} / "
            f"${MONTHLY_BUDGET_USD:.2f}). Skipping review.",
            file=sys.stderr,
        )
        sys.exit(0)

    client = AsyncOpenAI(api_key=openai_api_key)
    response = await client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or "{}"

    # Track cost
    usage = response.usage
    if usage:
        cost_tracker.record_call(usage.prompt_tokens, usage.completion_tokens)
        print(
            f"[COST] OpenAI fallback: {usage.prompt_tokens}+{usage.completion_tokens} tokens, "
            f"month total: ${cost_tracker.total_cost_usd:.4f}"
        )

    return json.loads(content)


async def submit_review(
    client: httpx.AsyncClient,
    repo: str,
    pr_number: int,
    commit_sha: str,
    review_result: dict,
    valid_lines_map: dict[str, set[int]],
) -> None:
    """Submit the AI review as a GitHub PR review from oct-support."""
    event_map = {
        "approve": "APPROVE",
        "request_changes": "REQUEST_CHANGES",
        "comment": "COMMENT",
    }
    verdict = review_result.get("verdict", "comment")
    event = event_map.get(verdict, "COMMENT")

    # Never approve without green CI — downgrade to COMMENT
    if event == "APPROVE":
        ci_passed, ci_failures = await get_ci_status(client, repo, commit_sha)
        if not ci_passed:
            failure_list = ", ".join(ci_failures[:5])
            print(f"[INFO] AI verdict was APPROVE but CI is not green ({failure_list}). Downgrading to COMMENT.")
            event = "COMMENT"

    # Hint for the PR author on how to trigger approve-check after resolving threads
    approve_hint = (
        "\n\n---\n"
        "💡 Once you've resolved all review threads, comment `/approve-check` to trigger auto-approval."
    )

    # Don't auto-approve on first review — always provide feedback first
    if event == "APPROVE" and not review_result.get("comments"):
        event = "APPROVE"
        body = f"✅ **AI Review — No issues found**\n\n{review_result.get('summary', 'Code looks good.')}"
    else:
        if event == "APPROVE":
            body = f"✅ **AI Review — Approved with comments**\n\n{review_result.get('summary', '')}"
        else:
            body = f"🔍 **AI Review — Changes requested**\n\n{review_result.get('summary', '')}"
            body += approve_hint

    # Build review comments — only keep those on valid diff lines
    comments = []
    dropped = []
    for c in review_result.get("comments", []):
        if not c.get("path") or not c.get("line"):
            continue
        path = c["path"]
        line = c["line"]
        valid_lines = valid_lines_map.get(path, set())
        if valid_lines and line not in valid_lines:
            # Find nearest valid line in the diff
            nearest = min(valid_lines, key=lambda vl: abs(vl - line)) if valid_lines else None
            if nearest and abs(nearest - line) <= 5:
                print(f"[INFO] Adjusted comment line {path}:{line} → {nearest} (nearest valid diff line)")
                line = nearest
            else:
                dropped.append(c)
                print(f"[WARN] Dropping comment on {path}:{line} — not in diff (valid: {sorted(valid_lines)[:10]}...)")
                continue
        comments.append({
            "path": path,
            "line": line,
            "side": c.get("side", "RIGHT"),
            "body": c["body"],
        })

    # Append dropped comments to body so nothing is lost
    if dropped:
        body += "\n\n---\n**Additional comments (not in diff, shown here):**\n"
        for c in dropped:
            body += f"\n**`{c['path']}` line {c['line']}:** {c['body']}\n"

    payload: dict = {"body": body, "event": event, "commit_id": commit_sha}
    if comments:
        payload["comments"] = comments

    resp = await client.post(
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=HEADERS,
        json=payload,
    )

    if resp.status_code == 422 and comments:
        # Log the actual error for debugging
        error_body = resp.text
        print(f"[WARN] Inline comments rejected (422): {error_body[:500]}", file=sys.stderr)
        print("[WARN] Retrying review without inline comments", file=sys.stderr)

        # Move all inline comments to body
        fallback_body = body
        if "\n**Additional comments" not in fallback_body:
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
    print(f"[OK] Review submitted: {event} with {len(comments)} inline comments"
          + (f" ({len(dropped)} dropped)" if dropped else ""))


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

    # Wait for CI to finish before approving
    print(f"[INFO] Waiting for CI checks on {commit_sha[:8]}...")
    ci_passed, ci_failures = await wait_for_ci(client, repo, commit_sha)
    if not ci_passed:
        failure_list = "\n".join(f"- {f}" for f in ci_failures)
        print(f"[INFO] CI checks not passing — cannot auto-approve:\n{failure_list}")
        # Post a comment explaining why approval is blocked
        payload = {
            "body": (
                "⏳ **Auto-approval blocked — CI checks not passing**\n\n"
                "All review threads are resolved, but the following checks are failing or pending:\n\n"
                f"{failure_list}\n\n"
                "Auto-approval will proceed once all CI checks pass."
            ),
            "event": "COMMENT",
            "commit_id": commit_sha,
        }
        resp = await client.post(
            f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
            headers=HEADERS,
            json=payload,
        )
        resp.raise_for_status()
        print(f"[OK] Posted CI-blocked comment on PR #{pr_number}.")
        return

    # Submit approval
    payload = {
        "body": "✅ **All review threads resolved & CI passing — auto-approved.**\n\nAll issues from the previous review have been addressed and all CI checks are green.",
        "event": "APPROVE",
        "commit_id": commit_sha,
    }
    resp = await client.post(
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=HEADERS,
        json=payload,
    )
    resp.raise_for_status()
    print(f"[OK] PR #{pr_number} approved by oct-support — all {len(bot_threads)} threads resolved, CI green.")


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

    # Initialize cost tracker
    cost_file = Path("/tmp/ai-cost-tracker/pr-review-cost.json")
    cost_tracker = CostTracker(cost_file)

    # Initialize rate limiter
    rate_file = Path("/tmp/ai-cost-tracker/pr-review-rate.json")
    rate_limiter = ReviewRateLimiter(rate_file)

    async with httpx.AsyncClient(
        headers={**HEADERS, "Authorization": f"Bearer {bot_pat}"},
        timeout=60.0,
    ) as client:
        if mode == "review":
            # Rate limit check
            pr_key = f"{repo}#{pr_number}"
            if not rate_limiter.check_and_record(pr_key):
                rate_limiter.save()
                return 0

            print(f"[INFO] Reviewing PR #{pr_number} in {repo}...")
            pr_details = await get_pr_details(client, repo, pr_number)
            files = await get_pr_files(client, repo, pr_number)
            commit_sha = pr_details["head"]["sha"]

            # Prevent duplicate reviews on the same commit
            if await has_bot_reviewed_commit(client, repo, pr_number, commit_sha):
                print(f"[INFO] Already reviewed commit {commit_sha[:8]} on PR #{pr_number}. Skipping.")
                rate_limiter.save()
                return 0

            reviewable = [f for f in files if not _should_skip(f["filename"])]
            if not reviewable:
                print("[INFO] No reviewable files changed. Skipping review.")
                return 0

            # Wait for CI to finish — CI results inform the review
            print(f"[INFO] Waiting for CI checks on {commit_sha[:8]}...")
            ci_passed, ci_failures = await wait_for_ci(client, repo, commit_sha)

            prompt = build_review_prompt(pr_details, files)

            # Include CI failures in prompt so AI considers them
            if not ci_passed:
                ci_context = "\n".join(f"- {f}" for f in ci_failures if "still " not in f)
                if ci_context:
                    prompt += (
                        "\n\n## CI Status — FAILING\n"
                        "The following CI checks are failing on this PR. "
                        "Factor this into your review — the code likely has bugs or test failures:\n"
                        f"{ci_context}\n"
                    )

            review_result = await run_ai_review(prompt, cost_tracker)
            valid_lines_map = _build_valid_lines_map(files)
            await submit_review(client, repo, pr_number, commit_sha, review_result, valid_lines_map)

            # Persist state
            cost_tracker.save()
            rate_limiter.save()

        elif mode == "approve":
            print(f"[INFO] Checking approval status for PR #{pr_number} in {repo}...")
            await check_and_approve(client, repo, pr_number)

        else:
            print(f"[ERROR] Unknown mode: {mode}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
