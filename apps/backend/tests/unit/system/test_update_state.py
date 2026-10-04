import json

from opencloudtouch.system import update_state


def test_get_update_status_defaults_to_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(
        update_state,
        "STATUS_PATH",
        tmp_path / "update-status.json",
    )
    monkeypatch.setattr(
        update_state,
        "__version__",
        "1.5.8",
    )

    assert update_state.get_update_status() == {
        "phase": "idle",
        "progress_pct": 0,
        "message": "No update in progress",
        "target_version": None,
        "current_version": "1.5.8",
    }


def test_set_and_get_update_status(tmp_path, monkeypatch):
    status_path = tmp_path / "update-status.json"

    monkeypatch.setattr(
        update_state,
        "STATUS_PATH",
        status_path,
    )
    monkeypatch.setattr(
        update_state,
        "__version__",
        "1.5.8",
    )

    update_state.set_update_status(
        "ready",
        progress_pct=100,
        message="Update complete",
        target_version="1.5.9",
        current_version="1.5.9",
        container_id="abc123",
    )

    assert update_state.get_update_status() == {
        "phase": "ready",
        "progress_pct": 100,
        "message": "Update complete",
        "target_version": "1.5.9",
        "current_version": "1.5.8",
        "container_id": "abc123",
    }


def test_get_update_status_handles_invalid_json(
    tmp_path,
    monkeypatch,
):
    status_path = tmp_path / "update-status.json"
    status_path.write_text("{broken", encoding="utf-8")

    monkeypatch.setattr(
        update_state,
        "STATUS_PATH",
        status_path,
    )
    monkeypatch.setattr(
        update_state,
        "__version__",
        "1.5.8",
    )

    assert update_state.get_update_status() == {
        "phase": "unknown",
        "progress_pct": 0,
        "message": "Update status unavailable",
        "target_version": None,
        "current_version": "1.5.8",
    }


def test_set_update_status_writes_valid_json(
    tmp_path,
    monkeypatch,
):
    status_path = tmp_path / "update-status.json"

    monkeypatch.setattr(
        update_state,
        "STATUS_PATH",
        status_path,
    )
    monkeypatch.setattr(
        update_state,
        "__version__",
        "1.5.8",
    )

    update_state.set_update_status(
        "pulling",
        progress_pct=25,
        message="Pulling new image...",
        target_version="1.5.9",
    )

    data = json.loads(
        status_path.read_text(encoding="utf-8")
    )

    assert data["phase"] == "pulling"
    assert data["progress_pct"] == 25
    assert data["target_version"] == "1.5.9"
    assert data["current_version"] == "1.5.8"
