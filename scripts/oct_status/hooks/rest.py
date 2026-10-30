"""Read-only GitHub REST access for the agent hooks (design section 8, E11: REST only).

Hooks run on contributor machines where only the Python standard library is guaranteed, so this module
uses ``urllib`` and nothing else. Every request has a 5 second timeout. The token comes from
``GITHUB_TOKEN``, ``GH_TOKEN`` or ``BOT_PAT``, else from ``gh auth token``; without one the requests are
anonymous (public repository, low rate limit). The token is never logged, echoed or put into a URL.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

API = "https://api.github.com"
TIMEOUT = 5.0
MAX_COMMENT_PAGES = 3
GUIDE_MARKER = "<!-- oct-next:v1 -->"
# Accounts that write the guide comment; mirrors `bot_logins` in config.yml (a test keeps them equal).
BOT_LOGINS = frozenset({"oct-support", "github-actions[bot]"})
_REMOTE = re.compile(r"[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")

# (url, headers) -> (status, body bytes); the default performs the request with urllib.
Opener = Callable[[str, Mapping[str, str]], tuple[int, bytes]]


class RestError(Exception):
    """A read failed (network, timeout, HTTP status >= 400 or invalid JSON)."""


def _urllib_open(url: str, headers: Mapping[str, str]) -> tuple[int, bytes]:  # pragma: no cover - real network
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def find_token(env: Mapping[str, str], run: Callable[..., Any] = subprocess.run) -> str | None:
    """A GitHub token from the environment or the gh CLI, or ``None`` (anonymous reads)."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN", "BOT_PAT"):
        if env.get(name, "").strip():
            return env[name].strip()
    try:
        done = run(["gh", "auth", "token"], capture_output=True, text=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    token = (done.stdout or "").strip() if done.returncode == 0 else ""
    return token or None


class Rest:
    """GET-only client for one repository."""

    def __init__(self, owner: str, repo: str, token: str | None = None, opener: Opener | None = None) -> None:
        self.owner, self.repo = owner, repo
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "oct-status-hook",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._open = opener or _urllib_open

    def get(self, path: str) -> Any:
        url = f"{API}/repos/{self.owner}/{self.repo}{path}"
        try:
            status, body = self._open(url, self._headers)
        except (OSError, ValueError) as exc:  # URLError and timeouts are OSError
            raise RestError(f"GET {path} failed ({type(exc).__name__})") from None
        if status >= 400:
            raise RestError(f"GET {path} answered {status}")
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError:
            raise RestError(f"GET {path} returned invalid JSON") from None

    def issue(self, number: int) -> dict:
        data = self.get(f"/issues/{number}")
        if not isinstance(data, dict):
            raise RestError(f"GET /issues/{number} returned no object")
        return data

    def guide_comment(self, number: int) -> dict | None:
        """The guide comment of an artifact (marker and bot author), or ``None`` when there is none."""
        for page in range(1, MAX_COMMENT_PAGES + 1):
            comments = self.get(f"/issues/{number}/comments?per_page=100&page={page}")
            if not isinstance(comments, list):
                raise RestError(f"GET /issues/{number}/comments returned no list")
            for comment in comments:
                login = ((comment or {}).get("user") or {}).get("login")
                if login in BOT_LOGINS and GUIDE_MARKER in (comment.get("body") or ""):
                    return comment
            if len(comments) < 100:
                return None
        return None

    def comment(self, comment_id: int) -> dict:
        data = self.get(f"/issues/comments/{comment_id}")
        if not isinstance(data, dict):
            raise RestError(f"GET /issues/comments/{comment_id} returned no object")
        return data

    def open_pull_for_head(self, branch: str) -> int | None:
        """Number of the open pull request whose head is `branch` in this repository, if exactly one."""
        pulls = self.get(f"/pulls?state=open&head={self.owner}:{urllib.parse.quote(branch, safe='')}")
        if not isinstance(pulls, list):
            raise RestError("GET /pulls returned no list")
        numbers = [p.get("number") for p in pulls if isinstance(p, dict) and isinstance(p.get("number"), int)]
        return numbers[0] if len(numbers) == 1 else None


def _git(args: list[str], cwd: Path, run: Callable[..., Any]) -> str | None:
    try:
        done = run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    out = (done.stdout or "").strip()
    return out if done.returncode == 0 and out else None


def origin_repo(cwd: Path, run: Callable[..., Any] = subprocess.run) -> tuple[str, str] | None:
    """(owner, repo) of the `origin` remote; also works for proxy URLs ending in ``/owner/repo``."""
    url = _git(["remote", "get-url", "origin"], cwd, run)
    match = _REMOTE.search(url or "")
    return (match[1], match[2]) if match else None


def current_branch(cwd: Path, run: Callable[..., Any] = subprocess.run) -> str | None:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd, run)
    return None if branch in (None, "HEAD") else branch


def project_dir(env: Mapping[str, str], event: Mapping[str, Any]) -> Path:
    return Path(env.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
