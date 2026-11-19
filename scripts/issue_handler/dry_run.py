"""Dry-run wrapper: reads go through, every write is only logged."""

from __future__ import annotations

import json
from typing import Any

WRITE_METHODS = {
    "add_labels",
    "post_comment",
    "close_issue",
    "set_assignee",
    "post_discussion_comment",
    "remove_label",
    "edit_comment",
    "reopen_issue",
    "mark_discussion_answer",
    "close_discussion",
}


class DryRunClient:
    def __init__(self, client: Any) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if name not in WRITE_METHODS:
            return attr

        async def log_only(*args: Any, **kwargs: Any) -> None:
            print(json.dumps({"dry_run": name, "args": [str(a)[:2000] for a in args]}), flush=True)

        return log_only
