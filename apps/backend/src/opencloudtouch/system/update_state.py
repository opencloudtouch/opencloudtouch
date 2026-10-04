import json
import os
from pathlib import Path
from typing import Any

from opencloudtouch import __version__


DB_PATH = Path(os.getenv("OCT_DB_PATH", "/data/oct.db"))
STATUS_PATH = DB_PATH.parent / "update-status.json"


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
        data = json.loads(
            STATUS_PATH.read_text(encoding="utf-8")
        )
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
