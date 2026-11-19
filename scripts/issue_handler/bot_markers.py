"""Hidden markers and the visible footer of bot comments."""

from __future__ import annotations

from typing import Any

ANSWER_MARKER = "<!-- oct-bot:answer -->"
SOLUTION_MARKER = "<!-- oct-bot:solution -->"
FOOTER = "_This is an automatic reply from the OpenCloudTouch support bot; a maintainer will follow up if needed._"


def finalize_comment(body: str, sources: list[Any] | None = None) -> str:
    """Add the sources list, the automatic-reply footer and the hidden answer marker."""
    if not body or ANSWER_MARKER in body:
        return body
    parts = [body.rstrip()]
    if sources:
        parts.append("**Sources:**\n" + "\n".join(f"- [{s.title}]({s.url})" for s in sources))
        parts.append(FOOTER)
    parts.append(ANSWER_MARKER)
    return "\n\n".join(parts)
