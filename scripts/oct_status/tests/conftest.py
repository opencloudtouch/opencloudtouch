"""Shared test helpers for oct_status."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx

from oct_status.model import Snapshot

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureTransport(httpx.MockTransport):
    """Replays recorded responses keyed ``"METHOD /path"`` (query string ignored).

    Unknown keys answer 404 with a JSON body, which makes "not found" paths testable.
    The collaborator-permission and compare endpoints are blocked in the capture
    environment and were never recorded; tests supply those as small synthetic
    ``extra`` routes. An ``extra`` value is a body (status 200) or ``(status, body)``.
    """

    def __init__(self, numbers: Iterable[int] = (), extra: dict[str, Any] | None = None) -> None:
        self.routes: dict[str, Any] = {}
        for number in numbers:
            self.routes.update(json.loads((FIXTURES / f"{number}.json").read_text(encoding="utf-8")))
        self.routes.update(extra or {})
        # `GET /pulls/{n}/commits` was never recorded: synthesize an empty list for every recorded PR
        # unless a test supplies its own route.
        for key in list(self.routes):
            match = re.fullmatch(r"GET (.*)/pulls/(\d+)", key)
            if match:
                self.routes.setdefault(f"GET {match[1]}/pulls/{match[2]}/commits", [])
        self.requests: list[str] = []
        super().__init__(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.path}"
        self.requests.append(key)
        if key not in self.routes:
            return httpx.Response(404, json={"message": "Not Found"})
        value = self.routes[key]
        if callable(value):  # synthetic route that looks at the request (e.g. paging)
            value = value(request)
        if isinstance(value, httpx.Response):  # synthetic route that needs headers (e.g. a Link header)
            return value
        if isinstance(value, tuple):
            status, body = value
            return httpx.Response(status, json=body)
        return httpx.Response(200, json=value)


def make_snapshot(**overrides: Any) -> Snapshot:
    """Build a Snapshot with neutral defaults; override any field by keyword."""
    values: dict[str, Any] = {
        "number": 1,
        "is_pr": False,
        "title": "",
        "body": "",
        "state": "open",
        "merged": False,
        "draft": False,
        "author": "someone",
        "author_permission": None,
        "labels": frozenset(),
        "base_ref": "",
        "head_ref": "",
        "head_sha": "",
        "reviews": (),
        "unresolved_threads": 0,
        "checks": (),
        "closing_refs": (),
        "sub_issues": (),
        "blocked_by": (),
        "pushes": (),
        "stack_drift": None,
        "head_is_fork": False,
    }
    values.update(overrides)
    return Snapshot(**values)
