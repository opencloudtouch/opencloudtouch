#!/usr/bin/env python3
"""Release-notes helper for the post-release workflow.

promote  CHANGELOG.md VERSION DATE [COMMITS_FILE]
    Turn "## [Unreleased]" into "## [VERSION] - DATE". The curated Unreleased text is
    kept; only when it is empty are notes built from the conventional-commit subjects in
    COMMITS_FILE (one per line).
extract  CHANGELOG.md VERSION
    Print the body of the "## [VERSION]" section.
"""
import re
import sys
from pathlib import Path

PLACEHOLDER = "_No changes yet._"
GROUPS = [("feat", "Added"), ("fix", "Fixed"), ("perf", "Performance"), ("refactor", "Changed"), ("docs", "Documentation")]
_COMMIT = re.compile(r"^(\w+)(?:\([^)]*\))?!?:\s*(.+)$")


def _split(text: str, heading: str):
    """Return (before, body, after) around the section that starts with `## [heading]`."""
    m = re.search(rf"^## \[{re.escape(heading)}\][^\n]*\n", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^## \[", text[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    return text[: m.end()], text[m.end():end], text[end:]


def _strip_separator(body: str) -> str:
    """Drop a trailing `---` rule only; dashes at the start of a bullet list stay."""
    return re.sub(r"(?:\n|^)-{3,}\s*$", "", body.strip()).strip()


def commit_notes(subjects) -> str:
    out = []
    for prefix, title in GROUPS:
        items = []
        for s in subjects:
            m = _COMMIT.match(s.strip())
            if m and m.group(1) == prefix:
                items.append(f"- {m.group(2)}")
        if items:
            out.append(f"### {title}\n" + "\n".join(items))
    return "\n\n".join(out)


def promote(text: str, version: str, date: str, subjects=()) -> str:
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.M):
        return text  # already promoted
    parts = _split(text, "Unreleased")
    if not parts:
        return text
    head, body, rest = parts
    body = _strip_separator(body)
    if not body or body == PLACEHOLDER:
        body = commit_notes(subjects)
    if not body:
        body = "### Changed\n- See the GitHub release notes."
    return f"{head}\n{PLACEHOLDER}\n\n---\n\n## [{version}] - {date}\n\n{body}\n\n---\n\n{rest.lstrip()}"


def extract(text: str, version: str) -> str:
    parts = _split(text, version)
    return _strip_separator(parts[1]) if parts else ""


if __name__ == "__main__":
    cmd, path = sys.argv[1], Path(sys.argv[2])
    content = path.read_text(encoding="utf-8")
    if cmd == "promote":
        version, date = sys.argv[3], sys.argv[4]
        subjects = Path(sys.argv[5]).read_text(encoding="utf-8").splitlines() if len(sys.argv) > 5 else []
        with path.open("w", encoding="utf-8", newline="\n") as out:
            out.write(promote(content, version, date, subjects))
    elif cmd == "extract":
        print(extract(content, sys.argv[3]))
    else:
        sys.exit(__doc__)
