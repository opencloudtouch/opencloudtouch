import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opencloudtouch import __version__

STATUS_PATH = Path(
    "/data/update-status.json"
)  # Persistent volume shared with update helper
ACTIVE_PHASES = frozenset({"pulling", "restarting", "rolling_back"})
ACTIVE_STATUS_TIMEOUT_SECONDS = 30 * 60


def _utc_now() -> datetime:
    return datetime.now(UTC)


def is_active_status_fresh(
    status: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a persisted in-progress state still owns the updater."""
    if status.get("phase") not in ACTIVE_PHASES:
        return False

    updated_at = status.get("updated_at")
    if not isinstance(updated_at, str):
        return False

    try:
        timestamp = datetime.fromisoformat(updated_at)
    except ValueError:
        return False

    if timestamp.tzinfo is None:
        return False

    age = (now or _utc_now()) - timestamp.astimezone(UTC)
    return age.total_seconds() <= ACTIVE_STATUS_TIMEOUT_SECONDS


def set_update_status(
    phase: str,
    *,
    progress_pct: int,
    message: str,
    target_version: str | None = None,
    current_version: str | None = None,
    **extra: Any,
) -> None:
    data = {
        "phase": phase,
        "progress_pct": progress_pct,
        "message": message,
        "target_version": target_version,
        "current_version": current_version or __version__,
        "updated_at": _utc_now().isoformat().replace("+00:00", "Z"),
        **extra,
    }

    tmp_path = STATUS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data), encoding="utf-8")
    tmp_path.replace(STATUS_PATH)


def get_update_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        return {
            "phase": "idle",
            "progress_pct": 0,
            "message": "No update in progress",
            "target_version": None,
            "current_version": __version__,
        }

    try:
        data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "phase": "unknown",
            "progress_pct": 0,
            "message": "Update status unavailable",
            "target_version": None,
            "current_version": __version__,
        }

    if not isinstance(data, dict):
        return {
            "phase": "unknown",
            "progress_pct": 0,
            "message": "Update status unavailable",
            "target_version": None,
            "current_version": __version__,
        }

    data["current_version"] = __version__
    return data
