"""Bug report API route — collects diagnostics and creates GitHub Issues."""

import gzip
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from opencloudtouch.api import github_client
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

_SECTION_SEPARATOR = "\n\n---\n\n"


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


class DiagnosticsRequest(BaseModel):
    """Request body for diagnostics download (no GitHub token needed)."""

    frontend_logs: list[dict] = []
    description: str = ""
    browser_info: str = ""
    current_route: str = ""
    click_timestamp: float = 0.0


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

    issue_url, issue_number = await github_client.create_github_issue(
        token=config.github_token,
        repo=config.github_repo,
        title=f"\U0001f41b [{request_body.installation_type}] {request_body.description[:70]}",
        body=body,
        labels=["bug", "user-report"],
    )

    # Upload logs as gzipped file to repo and link in issue body
    log_url = await github_client.upload_log_file(
        token=config.github_token,
        repo=config.github_repo,
        issue_number=issue_number,
        diagnostics=diagnostics,
        frontend_logs=request_body.frontend_logs,
    )

    # Upload screenshot as repo file
    screenshot_url = None
    if request_body.screenshot_data_url:
        try:
            screenshot_url = await github_client.upload_screenshot(
                token=config.github_token,
                repo=config.github_repo,
                issue_number=issue_number,
                data_url=request_body.screenshot_data_url,
            )
        except Exception:
            logger.debug("Could not upload screenshot to GitHub")

    # Update issue body with log + screenshot links if any were uploaded
    if log_url or screenshot_url:
        extras: list[str] = []
        if log_url:
            extras.append(
                f"## Logs\n\n"
                f"[Download backend + frontend logs (gzipped)]({log_url})"
            )
        if screenshot_url:
            extras.append(f"## Screenshot\n\n![Browser Screenshot]({screenshot_url})")
        body = body + _SECTION_SEPARATOR + _SECTION_SEPARATOR.join(extras)
        await github_client.update_issue_body(
            token=config.github_token,
            repo=config.github_repo,
            issue_number=issue_number,
            body=body,
        )

    logger.info("Bug report created: %s", issue_url)
    return BugReportResponse(issue_url=issue_url)


@router.post("/bug-report/diagnostics")
async def download_diagnostics(
    request_body: DiagnosticsRequest, request: Request
) -> Response:
    """Download a gzipped diagnostic bundle — works without GitHub token.

    The user can drag-drop the .log.gz file into a manually created GitHub issue.
    """
    diagnostics = await _collect_diagnostics(request, request_body.click_timestamp)
    log_text = github_client.build_log_text(
        diagnostics=diagnostics,
        frontend_logs=request_body.frontend_logs,
        extra_info={
            "description": request_body.description,
            "browser": request_body.browser_info,
            "route": request_body.current_route,
        },
    )
    if not log_text:
        log_text = "(no log data available)"

    compressed = gzip.compress(log_text.encode("utf-8"), compresslevel=9)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"oct-diagnostics-{timestamp}.log.gz"

    logger.debug(
        "Diagnostics download: %d chars → %d bytes gzip",
        len(log_text),
        len(compressed),
    )
    return Response(
        content=compressed,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Diagnostics collection
# ---------------------------------------------------------------------------


async def _collect_diagnostics(request: Request, click_timestamp: float = 0.0) -> dict:
    """Collect backend diagnostic data (anonymized, no secrets)."""
    from opencloudtouch import __version__

    config = get_config()

    devices = []
    device_id_lookup: dict[str, int] = {}  # device_id → DB id
    db_stats: dict[str, str | int] = {"presets": "?", "recents": "?", "devices": "?"}

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
    backend_logs = ring_buffer[-500:] if ring_buffer else []

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

    # Logs are uploaded as a gzipped file attachment after issue creation.
    # No placeholder needed — the link is added via body update.

    return "\n\n---\n\n".join(sections)


# Re-export extracted functions for backward compatibility with tests
_create_github_issue = github_client.create_github_issue
_upload_screenshot = github_client.upload_screenshot
_update_issue_body = github_client.update_issue_body
_upload_log_file = github_client.upload_log_file
_build_log_text = github_client.build_log_text
