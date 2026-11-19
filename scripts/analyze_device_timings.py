"""Summarise the device communication timings (PERF lines) of a backend log.

Usage:
    python scripts/analyze_device_timings.py <log file or URL> [--top 25]
    python scripts/analyze_device_timings.py http://hera:7778/api/logs/backend  (plain text; unzip first if the server returns a ZIP)

Reads the ``PERF kind=... name=... operation=... ms=...`` lines written by
``opencloudtouch.core.device_timing`` and prints, per wizard operation, the total time and the
slowest SSH commands, so that performance work can start where the time is actually spent.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from collections import defaultdict

LINE = re.compile(r"PERF (?P<body>.+)$")
FIELD = re.compile(r"(\w+)=(.*?)(?= \w+=|$)")


def load(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=60) as resp:  # noqa: S310 - LAN URL given by the user
            return resp.read().decode("utf-8", errors="replace")
    with open(source, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse(text: str) -> list[dict[str, str]]:
    entries = []
    for raw in text.splitlines():
        m = LINE.search(raw)
        if m:
            entries.append(dict(FIELD.findall(m.group("body"))))
    return entries


def stats(values: list[float]) -> str:
    return f"n={len(values):<4} total={sum(values) / 1000:8.1f}s avg={sum(values) / len(values):9.0f}ms max={max(values):9.0f}ms"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    entries = parse(load(args.source))
    if not entries:
        print("No PERF lines found (is the backend running a build with device timing?)")
        return 1

    print("# Device communication timings\n")
    print("## Wizard operations (end to end)")
    ops = defaultdict(list)
    for e in entries:
        if e.get("kind") == "operation":
            ops[e["name"]].append(float(e["ms"]))
    for name, vals in sorted(ops.items(), key=lambda kv: -sum(kv[1])):
        print(f"- {name:28} {stats(vals)}")

    print("\n## SSH sessions and connects")
    for kind in ("ssh_session", "ssh_connect"):
        groups = defaultdict(list)
        for e in entries:
            if e.get("kind") == kind:
                groups[e["name"]].append(float(e["ms"]))
        for name, vals in sorted(groups.items(), key=lambda kv: -sum(kv[1])):
            print(f"- {kind:12} {name:28} {stats(vals)}")

    print(f"\n## Slowest SSH commands (top {args.top}, grouped by operation and command)")
    cmds = defaultdict(list)
    for e in entries:
        if e.get("kind") == "ssh_exec":
            cmds[(e.get("operation", ""), e["name"])].append(float(e["ms"]))
    ranked = sorted(cmds.items(), key=lambda kv: -sum(kv[1]))[: args.top]
    for (op, name), vals in ranked:
        print(f"- [{op or '-'}] {name[:90]}\n    {stats(vals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
