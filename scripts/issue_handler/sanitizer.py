"""Prompt injection sanitizer (T013).

Protects against prompt injection by:
1. Stripping code fences with role keywords (system, assistant, user)
2. Truncating to 4000 chars max
3. Removing existing XML delimiter tags to prevent nesting
"""

from __future__ import annotations

import re

MAX_INPUT_LENGTH = 4000

# Code fences with role keywords that could simulate system prompts
ROLE_FENCE_PATTERN = re.compile(
    r"```(?:system|assistant|user)\s*\n.*?```",
    re.DOTALL | re.IGNORECASE,
)

# XML delimiter tags used in the prompt template
DELIMITER_TAGS = re.compile(
    r"</?user_issue_(?:title|body)>",
    re.IGNORECASE,
)


def sanitize_input(text: str | None, *, is_title: bool = False) -> str:
    """Sanitize user-provided text for safe inclusion in AI prompts.

    Args:
        text: Raw user input (title or body). None is treated as empty.
        is_title: Whether this is a title (unused, for future differentiation).

    Returns:
        Sanitized text safe for prompt inclusion.
    """
    if text is None:
        return ""

    # Strip code fences with role keywords
    result = ROLE_FENCE_PATTERN.sub("", text)

    # Remove any existing XML delimiter tags to prevent nesting attacks
    result = DELIMITER_TAGS.sub("", result)

    # Truncate to max length
    if len(result) > MAX_INPUT_LENGTH:
        result = result[:MAX_INPUT_LENGTH]

    return result
