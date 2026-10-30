"""Record sanitized REST responses of one issue or pull request as a JSON fixture.

Read-only. Usage (needs a token in ``GITHUB_TOKEN``)::

    python -m oct_status.tools.capture_fixture opencloudtouch/opencloudtouch 574 out.json

The fixture maps ``"GET /repos/o/r/pulls/574"`` to a sanitized response. Only titles,
labels, states, the draft flag, author logins, refs, SHAs, review states, check names,
conclusions, app slugs and relation phrases (``Closes``/``Part of``/``Depends on`` plus references) and bare ``#<n>`` references from the body
are kept. Free text, URLs, e-mail addresses and IP addresses are dropped.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import httpx

API_ROOT = "https://api.github.com"
RELATION = re.compile(r"\b(?:Closes|Part of|Depends on)\s+#\w+(?:(?:,|\s+and)?\s+#\w+)*", re.IGNORECASE)
REFERENCE = re.compile(r"#\d+")


def sanitize_body(body: str | None) -> str:
    """Reduce a body to its relation phrases and bare ``#<n>`` references (no free text)."""
    kept: list[str] = []
    for line in (body or "").splitlines():
        phrases = RELATION.findall(line)
        rest = RELATION.sub(" ", line)
        refs = REFERENCE.findall(rest)
        if phrases:
            kept.extend(phrases)
        if refs:
            kept.append("See " + ", ".join(refs))
    return "\n".join(kept)


def _user(u: dict[str, Any] | None) -> dict[str, Any] | None:
    return {"login": u["login"]} if u else None


def sanitize_issue(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "number": d["number"],
        "title": d["title"],
        "state": d["state"],
        "user": _user(d.get("user")),
        "labels": [{"name": lb["name"]} for lb in d.get("labels", [])],
        "body": sanitize_body(d.get("body")),
        "author_association": d.get("author_association"),
    }
    if "pull_request" in d:
        out["pull_request"] = {}
    return out


def sanitize_pull(d: dict[str, Any]) -> dict[str, Any]:
    out = sanitize_issue(d)
    out.update(
        {
            "draft": d.get("draft", False),
            "merged": d.get("merged", False),
            "base": {"ref": d["base"]["ref"]},
            "head": {"ref": d["head"]["ref"], "sha": d["head"]["sha"]},
        }
    )
    return out


def sanitize_reviews(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"user": _user(r.get("user")), "state": r["state"], "commit_id": r.get("commit_id")} for r in items]


def sanitize_checks(d: dict[str, Any]) -> dict[str, Any]:
    runs = [
        {
            "name": c["name"],
            "status": c["status"],
            "conclusion": c.get("conclusion"),
            "app": {"slug": (c.get("app") or {}).get("slug", "")},
        }
        for c in d.get("check_runs", [])
    ]
    return {"total_count": len(runs), "check_runs": runs}


def capture(repo: str, number: int, token: str) -> dict[str, Any]:
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    fixture: dict[str, Any] = {}
    with httpx.Client(base_url=API_ROOT, headers=headers, timeout=30.0) as client:

        def get(path: str) -> Any:
            resp = client.get(path, params={"per_page": 100})
            resp.raise_for_status()
            return resp.json()

        base = f"/repos/{repo}"
        issue = get(f"{base}/issues/{number}")
        if "pull_request" in issue:
            pull = get(f"{base}/pulls/{number}")
            fixture[f"GET {base}/pulls/{number}"] = sanitize_pull(pull)
            fixture[f"GET {base}/pulls/{number}/reviews"] = sanitize_reviews(get(f"{base}/pulls/{number}/reviews"))
            sha = pull["head"]["sha"]
            fixture[f"GET {base}/commits/{sha}/check-runs"] = sanitize_checks(get(f"{base}/commits/{sha}/check-runs"))
        else:
            fixture[f"GET {base}/issues/{number}"] = sanitize_issue(issue)
    return fixture


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: capture_fixture.py <owner/repo> <number> <out.json>", file=sys.stderr)
        return 2
    data = capture(argv[1], int(argv[2]), os.environ["GITHUB_TOKEN"])
    with open(argv[3], "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
