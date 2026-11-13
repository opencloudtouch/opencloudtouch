"""Timing of device communication (SSH connect, SSH commands, wizard operations).

Every measurement is logged on the ``opencloudtouch.perf`` logger as one ``PERF`` line with
``key=value`` pairs (so it is part of the downloadable backend log) and kept in a small in-memory
ring buffer. Setting ``OCT_PERF_LOG`` to a file path additionally appends one JSON object per
measurement, which makes later analysis (for example finding the slowest backup step) easy.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

perf_logger = logging.getLogger("opencloudtouch.perf")

_MAX_ENTRIES = 5000
_entries: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)

# Name of the wizard operation (e.g. "backup", "check-usb") that the current task is running.
current_operation: ContextVar[str] = ContextVar("oct_perf_operation", default="")


def _command_label(command: str, limit: int = 120) -> str:
    """Single-line, truncated command text (no full command lines in the log)."""
    one_line = " ".join(command.split())
    return one_line if len(one_line) <= limit else one_line[: limit - 1] + "…"


def record(kind: str, name: str, duration_ms: float, **fields: Any) -> None:
    """Record one timing. Never raises."""
    try:
        entry: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "kind": kind,
            "name": name,
            "operation": current_operation.get(),
            "ms": round(duration_ms, 1),
            **fields,
        }
        _entries.append(entry)
        perf_logger.info(
            "PERF %s",
            " ".join(f"{k}={v}" for k, v in entry.items() if k != "ts" and v != ""),
        )
        path = os.getenv("OCT_PERF_LOG")
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - measuring must never break the device operation
        pass


@contextmanager
def measure(kind: str, name: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Measure a block. The yielded dict can be filled with extra fields (e.g. ``ok``)."""
    extra: dict[str, Any] = dict(fields)
    start = time.perf_counter()
    try:
        yield extra
    finally:
        record(kind, name, (time.perf_counter() - start) * 1000, **extra)


@contextmanager
def operation(name: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Measure a whole wizard operation; SSH timings inside carry its name."""
    token = current_operation.set(name)
    try:
        with measure("operation", name, **fields) as extra:
            yield extra
    finally:
        current_operation.reset(token)


def command_label(command: str) -> str:
    return _command_label(command)


def recent_entries() -> list[dict[str, Any]]:
    """Snapshot of the ring buffer (oldest first)."""
    return list(_entries)


def clear() -> None:
    _entries.clear()
