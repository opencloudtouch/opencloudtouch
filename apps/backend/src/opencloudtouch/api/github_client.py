"""GitHub API client for bug report issue creation and file uploads.

Extracted from api/bug_report.py to separate GitHub API concerns
from route handling and diagnostics collection.
"""

import base64
import gzip
import logging

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def create_github_issue(
    token: str, repo: str, title: str, body: str, labels: list[str]
) -> tuple[str, int]:
    """Create a GitHub Issue via REST API. Returns (html_url, issue_number)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers=_github_headers(token),
            json={"title": title, "body": body, "labels": labels},
            timeout=15.0,
        )
        if response.status_code != 201:
            logger.error(
                "GitHub API error: %d — %s",
                response.status_code,
                response.text[:200],
            )
            raise HTTPException(
                status_code=502,
                detail=f"GitHub API error: {response.status_code}",
            )
        data = response.json()
        return data["html_url"], data["number"]


async def upload_screenshot(
    token: str, repo: str, issue_number: int, data_url: str
) -> str | None:
    """Upload screenshot to repo via Contents API, return raw URL."""
    if ";base64," not in data_url:
        return None
    raw_b64 = data_url.split(";base64,", 1)[1]

    path = f".github/bug-screenshots/issue-{issue_number}.jpg"
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            headers=_github_headers(token),
            json={
                "message": f"screenshot for #{issue_number}",
                "content": raw_b64,
            },
            timeout=30.0,
        )
        if response.status_code not in (200, 201):
            logger.warning(
                "Screenshot upload failed: %d — %s",
                response.status_code,
                response.text[:200],
            )
            return None
        return response.json()["content"]["download_url"]


async def update_issue_body(
    token: str, repo: str, issue_number: int, body: str
) -> None:
    """Update the body of an existing issue."""
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}",
            headers=_github_headers(token),
            json={"body": body},
            timeout=15.0,
        )


async def upload_log_file(
    token: str,
    repo: str,
    issue_number: int,
    diagnostics: dict,
    frontend_logs: list[dict],
) -> str | None:
    """Build a combined log file, gzip it, upload to repo via Contents API.

    Returns the download URL, or None on failure.
    """
    log_text = build_log_text(diagnostics, frontend_logs)
    if not log_text:
        return None

    compressed = gzip.compress(log_text.encode("utf-8"), compresslevel=9)
    b64_content = base64.b64encode(compressed).decode("ascii")

    logger.debug(
        "Log file: %d chars text → %d bytes gzip → %d chars base64",
        len(log_text),
        len(compressed),
        len(b64_content),
    )

    path = f".github/bug-logs/issue-{issue_number}.log.gz"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"https://api.github.com/repos/{repo}/contents/{path}",
                headers=_github_headers(token),
                json={
                    "message": f"bug report logs for #{issue_number}",
                    "content": b64_content,
                },
                timeout=30.0,
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Log file upload failed: %d — %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None
            return resp.json()["content"]["download_url"]
    except Exception as exc:
        logger.warning("Log file upload error: %s", exc)
        return None


def build_log_text(
    diagnostics: dict,
    frontend_logs: list[dict],
    extra_info: dict | None = None,
) -> str:
    """Build combined plain-text log content from diagnostics."""
    parts: list[str] = []

    parts.append("=== OCT Diagnostic Bundle ===")
    parts.append(f"Version: {diagnostics.get('backend_version', '?')}")
    parts.append(f"Timestamp: {diagnostics.get('timestamp', '?')}")
    if extra_info:
        parts.extend(f"{k}: {v}" for k, v in extra_info.items() if v)
    parts.append("")

    _append_dict_section(parts, diagnostics, "devices", _format_devices)
    _append_dict_section(parts, diagnostics, "db_stats", _format_key_value, "DB Stats")
    _append_dict_section(parts, diagnostics, "config", _format_key_value, "Config")

    be_logs = diagnostics.get("backend_logs", [])
    if be_logs:
        parts.append(f"=== Backend Logs ({len(be_logs)} entries) ===")
        parts.extend(str(e) for e in be_logs)
        parts.append("")

    if frontend_logs:
        trimmed = frontend_logs[-500:]
        parts.append(f"=== Frontend Logs ({len(trimmed)} entries) ===")
        for e in trimmed:
            parts.append(
                f"[{e.get('timestamp', '')}] {e.get('level', '')}: {e.get('message', '')}"
            )
        parts.append("")

    return "\n".join(parts) if parts else ""


def _append_dict_section(
    parts: list[str],
    diagnostics: dict,
    key: str,
    formatter,
    title: str | None = None,
) -> None:
    """Append a diagnostics section if data exists."""
    data = diagnostics.get(key, {} if key != "devices" else [])
    if data:
        formatter(parts, data, title or key.replace("_", " ").title())
        parts.append("")


def _format_devices(parts: list[str], devices: list, title: str) -> None:
    parts.append(f"=== {title} ({len(devices)}) ===")
    for d in devices:
        parts.append(
            f"  {d.get('name', '?')} (ID {d.get('uuid', '?')}) — {d.get('ip', '?')}"
        )


def _format_key_value(parts: list[str], data: dict, title: str) -> None:
    parts.append(f"=== {title} ===")
    for k, v in data.items():
        parts.append(f"  {k}: {v}")
