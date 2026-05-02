"""Bug report API route — collects diagnostics and creates GitHub Issues."""

import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from opencloudtouch.core.config import get_config
from opencloudtouch.core.logging import get_log_entries


def _anonymize_ip(ip: str) -> str:
    """Mask middle octets of an IPv4 address: 192.168.178.88 → 192.x.x.88"""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.x.x.{parts[3]}"
    return ip


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["bug-report"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BugReportRequest(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    steps_to_reproduce: str = Field(min_length=10, max_length=2000)
    expected_behavior: str = Field(min_length=5, max_length=1000)
    installation_type: str
    hardware: str
    soundtouch_devices: list[str] = []
    network_config: str = ""
    additional_info: str = ""
    other_installation: str = ""
    other_hardware: str = ""
    other_device: str = ""
    screenshot_data_url: str = ""
    frontend_logs: list[dict] = []
    browser_info: str = ""
    current_route: str = ""
    click_timestamp: float = 0.0


class BugReportResponse(BaseModel):
    issue_url: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/bug-report", response_model=BugReportResponse)
async def create_bug_report(request_body: BugReportRequest, request: Request):
    """Create a bug report as a GitHub Issue with auto-collected diagnostics."""
    config = get_config()
    if not config.github_token:
        raise HTTPException(
            status_code=503,
            detail="Bug reporting is not configured. Set OCT_GITHUB_TOKEN.",
        )

    diagnostics = await _collect_diagnostics(request, request_body.click_timestamp)
    body = _build_issue_body(request_body, diagnostics)

    # Truncate to GitHub's 65536 char limit
    if len(body) > 64000:
        body = body[:64000] + "\n\n---\n*Truncated: body exceeded 64KB limit*"

    issue_url, issue_number = await _create_github_issue(
        token=config.github_token,
        repo=config.github_repo,
        title=f"\U0001f41b [{request_body.installation_type}] {request_body.description[:70]}",
        body=body,
        labels=["bug", "user-report"],
    )

    # Upload screenshot as repo file and edit issue body to reference it
    if request_body.screenshot_data_url:
        try:
            screenshot_url = await _upload_screenshot(
                token=config.github_token,
                repo=config.github_repo,
                issue_number=issue_number,
                data_url=request_body.screenshot_data_url,
            )
            if screenshot_url:
                screenshot_md = (
                    f"## Screenshot\n\n![Browser Screenshot]({screenshot_url})"
                )
                body = body + f"\n\n---\n\n{screenshot_md}"
                await _update_issue_body(
                    token=config.github_token,
                    repo=config.github_repo,
                    issue_number=issue_number,
                    body=body,
                )
        except Exception:
            logger.debug("Could not upload screenshot to GitHub")

    logger.info(f"Bug report created: {issue_url}")
    return BugReportResponse(issue_url=issue_url)


# ---------------------------------------------------------------------------
# Diagnostics collection
# ---------------------------------------------------------------------------


async def _collect_diagnostics(request: Request, click_timestamp: float = 0.0) -> dict:
    """Collect backend diagnostic data (anonymized, no secrets)."""
    from opencloudtouch import __version__

    config = get_config()

    devices = []
    device_id_lookup: dict[str, int] = {}  # device_id → DB id
    db_stats = {"presets": "?", "recents": "?", "devices": "?"}

    try:
        device_repo = request.app.state.device_repo
        all_devices = await device_repo.get_all()
        for d in all_devices:
            device_id_lookup[d.device_id] = d.id
        devices = [
            {
                "name": d.name,
                "uuid": d.id,
                "ip": _anonymize_ip(d.ip),
            }
            for d in all_devices
        ]
        db_stats["devices"] = len(all_devices)
    except Exception:
        logger.debug("Could not collect device info for bug report")

    try:
        preset_repo = request.app.state.preset_repo
        total_presets = 0
        for d_id in device_id_lookup:
            presets = await preset_repo.get_all_presets(d_id)
            total_presets += len(presets)
        db_stats["presets"] = total_presets
    except Exception:
        logger.debug("Could not collect preset count for bug report")

    try:
        recents_repo = request.app.state.recents_repo
        total_recents = 0
        for d_id in device_id_lookup:
            recents = await recents_repo.get_recents(d_id)
            total_recents += len(recents)
        db_stats["recents"] = total_recents
    except Exception:
        logger.debug("Could not collect recents count for bug report")

    ring_buffer = get_log_entries()
    backend_logs = ring_buffer[-100:] if ring_buffer else []

    # Anonymize manual_device_ips
    anon_ips = [_anonymize_ip(ip) for ip in config.manual_device_ips]

    return {
        "backend_version": __version__,
        "backend_logs": backend_logs,
        "config": {
            "discovery_enabled": config.discovery_enabled,
            "mock_mode": config.mock_mode,
            "log_level": config.log_level,
            "manual_device_ips": anon_ips,
        },
        "devices": devices,
        "db_stats": db_stats,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------


def _build_issue_body(req: BugReportRequest, diag: dict) -> str:
    """Build structured Markdown issue body."""
    devices_str = (
        ", ".join(req.soundtouch_devices) if req.soundtouch_devices else "Not specified"
    )
    network_labels = {"wifi": "Wi-Fi", "lan": "LAN", "mixed": "Mixed"}

    # Append "Other" details
    install_str = req.installation_type
    if req.other_installation:
        install_str += f" ({req.other_installation})"
    hw_str = req.hardware
    if req.other_hardware:
        hw_str += f" ({req.other_hardware})"
    if req.other_device:
        devices_str += f" ({req.other_device})"

    sections = [
        f"## Bug Description\n\n{req.description}",
        f"## Steps to Reproduce\n\n{req.steps_to_reproduce}",
        f"## Expected Behavior\n\n{req.expected_behavior}",
        (
            f"## Environment\n\n"
            f"| | |\n|---|---|\n"
            f"| **OCT Version** | Backend v{diag['backend_version']} |\n"
            f"| **Installation Type** | {install_str} |\n"
            f"| **Hardware** | {hw_str} |\n"
            f"| **SoundTouch Device(s)** | {devices_str} |\n"
            f"| **Network** | {network_labels.get(req.network_config, req.network_config or 'Not specified')} |\n"
            f"| **Browser** | {req.browser_info} |\n"
            f"| **Route** | {req.current_route} |\n"
            f"| **Timestamp** | {diag.get('timestamp', 'N/A')} |"
        ),
    ]

    if req.additional_info:
        sections.append(f"## Additional Info\n\n{req.additional_info}")

    # Screenshot placeholder — actual image is uploaded separately after issue creation

    # Device Status
    if diag.get("devices"):
        device_lines = "\n".join(
            f"- {d['name']} (ID {d['uuid']}) — {d.get('ip', 'unknown')}"
            for d in diag["devices"]
        )
        sections.append(f"## Device Status\n\n{device_lines}")

    # DB Stats
    stats = diag.get("db_stats", {})
    if stats:
        sections.append(
            f"## DB Statistics\n\n"
            f"- Presets: {stats.get('presets', '?')}\n"
            f"- Recents: {stats.get('recents', '?')}\n"
            f"- Devices: {stats.get('devices', '?')}"
        )

    # Config (sanitized)
    cfg = diag.get("config", {})
    if cfg:
        config_str = "\n".join(f"- {k}: `{v}`" for k, v in cfg.items())
        sections.append(f"## Configuration\n\n{config_str}")

    # Frontend Logs
    if req.frontend_logs:
        log_lines = "\n".join(
            f"[{entry.get('timestamp', '')}] {entry.get('level', '')}: {entry.get('message', '')}"
            for entry in req.frontend_logs[-100:]
        )
        sections.append(f"## Frontend Logs (last 100)\n\n```\n{log_lines}\n```")

    # Backend Logs (captured before user clicked 'Report a Bug')
    be_logs = diag.get("backend_logs", [])
    if be_logs:
        log_lines = "\n".join(
            f"[{entry.get('timestamp', '')}] {entry.get('level', '')}: {entry.get('message', '')}"
            for entry in be_logs
        )
        sections.append(
            f"## Backend Logs (last 100 before report)\n\n```\n{log_lines}\n```"
        )

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------


async def _create_github_issue(
    token: str, repo: str, title: str, body: str, labels: list[str]
) -> tuple[str, int]:
    """Create a GitHub Issue via REST API. Returns (html_url, issue_number)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "body": body, "labels": labels},
            timeout=15.0,
        )
        if response.status_code != 201:
            logger.error(
                f"GitHub API error: {response.status_code} — {response.text[:200]}"
            )
            raise HTTPException(
                status_code=502,
                detail=f"GitHub API error: {response.status_code}",
            )
        data = response.json()
        return data["html_url"], data["number"]


async def _upload_screenshot(
    token: str, repo: str, issue_number: int, data_url: str
) -> str | None:
    """Upload screenshot to repo via Contents API, return raw URL."""

    # Parse data URL: "data:image/jpeg;base64,/9j/..."
    if ";base64," not in data_url:
        return None
    raw_b64 = data_url.split(";base64,", 1)[1]

    path = f".github/bug-screenshots/issue-{issue_number}.jpg"
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "message": f"screenshot for #{issue_number}",
                "content": raw_b64,
            },
            timeout=30.0,
        )
        if response.status_code not in (200, 201):
            logger.warning(
                f"Screenshot upload failed: {response.status_code} — {response.text[:200]}"
            )
            return None
        return response.json()["content"]["download_url"]


async def _update_issue_body(
    token: str, repo: str, issue_number: int, body: str
) -> None:
    """Update the body of an existing issue."""
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"body": body},
            timeout=15.0,
        )
