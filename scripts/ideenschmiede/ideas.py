"""Pure helpers for the Ideenschmiede: idea files, discussion text, sticky overview.

Standard library only; no network access here (see main.py for the GitHub calls).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

STICKY_MARKER = "<!-- oct-ideenschmiede-sticky:v1 -->"
_IDEA_MARKER_RE = re.compile(r"<!-- oct-idea:([A-Za-z0-9_-]+) -->")
_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)

# Furthest progress first; "declined" is handled separately because it overrides.
_STATUS_ORDER = ("specced", "accepted")
DECIDED = {"accepted", "specced", "declined"}


@dataclass(frozen=True)
class Idea:
    id: str
    title: str
    summary: str
    body: str


def parse_idea(text: str) -> Idea:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError("idea file needs a front matter block")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    if not meta.get("id") or not meta.get("title"):
        raise ValueError("idea front matter needs 'id' and 'title'")
    return Idea(id=meta["id"], title=meta["title"], summary=meta.get("summary", ""), body=match.group(2))


def load_ideas(directory: Path) -> list[Idea]:
    ideas = [parse_idea(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.md"))]
    return sorted(ideas, key=lambda idea: idea.id)


def idea_marker(idea_id: str) -> str:
    return f"<!-- oct-idea:{idea_id} -->"


def idea_id_from_body(body: str | None) -> str | None:
    match = _IDEA_MARKER_RE.search(body or "")
    return match.group(1) if match else None


def discussion_body(idea: Idea, repo: str) -> str:
    source = f"https://github.com/{repo}/blob/main/docs/ideenschmiede/ideas"
    return (
        f"{idea_marker(idea.id)}\n"
        f"> {idea.summary}\n\n"
        f"{idea.body.strip()}\n\n"
        "---\n\n"
        "**Your vote counts.** Use the upvote button (or 👍) if you want this, 👎 if you do not, "
        "and tell us why in the comments. This is a discussion, not a spec: nothing here is decided "
        "until a maintainer labels it `idea:accepted`.\n\n"
        f"Source text: [`docs/ideenschmiede/ideas`]({source}) · How it works: "
        f"[Ideenschmiede README](https://github.com/{repo}/blob/main/docs/ideenschmiede/README.md)\n"
    )


def status_from_labels(labels: list[str]) -> str:
    names = {label.removeprefix("idea:") for label in labels if label.startswith("idea:")}
    if "declined" in names:
        return "declined"
    for status in _STATUS_ORDER:
        if status in names:
            return status
    return "open"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _table(rows: list[dict], with_status: bool) -> list[str]:
    head = "| # | Idea | 👍 | 👎 | 💬 |" + (" Status |" if with_status else "")
    sep = "|---|---|---|---|---|" + ("---|" if with_status else "")
    lines = [head, sep]
    for row in rows:
        line = (
            f"| #{row['number']} | [{_cell(row['title'])}]({row['url']}) | "
            f"{row['upvotes']} | {row['downvotes']} | {row['comments']} |"
        )
        if with_status:
            line += f" {status_from_labels(row['labels'])} |"
        lines.append(line)
    return lines


def render_sticky(rows: list[dict], repo: str, generated: str) -> str:
    open_rows = [r for r in rows if status_from_labels(r["labels"]) not in DECIDED]
    decided_rows = [r for r in rows if status_from_labels(r["labels"]) in DECIDED]
    open_rows.sort(key=lambda r: (-(r["upvotes"] - r["downvotes"]), -r["comments"], r["number"]))
    decided_rows.sort(key=lambda r: r["number"])

    out = [
        STICKY_MARKER,
        "# Ideenschmiede",
        "",
        (
            "Ideas for OpenCloudTouch, open for debate and votes. Kept up to date by a workflow; "
            "please do not edit this issue by hand. "
            f"[How it works](https://github.com/{repo}/blob/main/docs/ideenschmiede/README.md) · "
            f"[All ideas](https://github.com/{repo}/discussions/categories/ideenschmiede)"
        ),
        "",
        "### Open for debate",
        "",
    ]
    if rows:
        out += _table(open_rows, with_status=False) if open_rows else ["_Nothing open._"]
    else:
        out.append("_No ideas yet._")
    if decided_rows:
        out += ["", "### Decided", ""] + _table(decided_rows, with_status=True)
    out += ["", f"_Last updated {generated}._", ""]
    return "\n".join(out)
