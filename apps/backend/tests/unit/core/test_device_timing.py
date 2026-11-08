"""Tests for the device communication timing helper."""

import json
import logging

from opencloudtouch.core import device_timing


def setup_function():
    device_timing.clear()


def test_record_keeps_entry_and_logs_perf_line(caplog):
    with caplog.at_level(logging.INFO, logger="opencloudtouch.perf"):
        device_timing.record("ssh_exec", "ls /media", 12.34, ok=True)

    entries = device_timing.recent_entries()
    assert entries[-1]["kind"] == "ssh_exec"
    assert entries[-1]["ms"] == 12.3
    assert any("PERF kind=ssh_exec name=ls /media" in m for m in caplog.messages)


def test_operation_name_is_attached_to_inner_timings():
    with device_timing.operation("backup"):
        device_timing.record("ssh_exec", "tar", 1.0)
    inner = [e for e in device_timing.recent_entries() if e["kind"] == "ssh_exec"][0]
    outer = [e for e in device_timing.recent_entries() if e["kind"] == "operation"][0]
    assert inner["operation"] == "backup"
    assert outer["name"] == "backup"
    assert device_timing.current_operation.get() == ""


def test_command_label_is_single_line_and_truncated():
    label = device_timing.command_label("tar czf\n  /a/b " + "x" * 300)
    assert "\n" not in label
    assert len(label) <= 120


def test_jsonl_file_written_when_configured(tmp_path, monkeypatch):
    target = tmp_path / "perf.jsonl"
    monkeypatch.setenv("OCT_PERF_LOG", str(target))
    device_timing.record("ssh_connect", "10.0.0.1", 5.0, ok=True)
    line = json.loads(target.read_text(encoding="utf-8").strip())
    assert line["kind"] == "ssh_connect"


def test_record_never_raises(monkeypatch):
    monkeypatch.setenv("OCT_PERF_LOG", "/nonexistent-dir/x/perf.jsonl")
    device_timing.record("ssh_exec", "x", 1.0)
