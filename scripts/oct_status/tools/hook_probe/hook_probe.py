"""Feasibility probe for the agent hooks (Task 15; removed again in Task 16).

Answers two questions:
1. Is `updatedInput` of a PreToolUse hook honoured? (the Bash command is rewritten to `echo rewritten`)
2. Do hooks fire for tool calls made by a subagent? (every call appends a line to the log)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("/tmp/hook-probe.log")


def main() -> int:
    event = json.load(sys.stdin)
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool_name": event.get("tool_name"),
        "session_id": event.get("session_id"),
        "agent_id": event.get("agent_id"),
        "command": (event.get("tool_input") or {}).get("command"),
    }
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": {"command": "echo rewritten"},
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
