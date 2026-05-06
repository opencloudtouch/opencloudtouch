"""KB article generator — AI-powered draft creation from closed issues (T038).

Fetches issue + comments, generates a KB article draft using AI,
validates frontmatter, and writes to approved_answers/ with _draft_ prefix.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "kb_generator_prompt.md"
OUTPUT_DIR = Path(__file__).parent / "approved_answers"


def load_prompt() -> str:
    """Load the KB generator prompt template."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def validate_frontmatter(content: str) -> bool:
    """Validate that generated content has valid YAML frontmatter."""
    match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return False
    try:
        meta = yaml.safe_load(match.group(1))
        return isinstance(meta, dict) and "tags" in meta and "title" in meta
    except yaml.YAMLError:
        return False


def sanitize_filename(title: str) -> str:
    """Convert a title to a safe filename."""
    name = title.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")[:60]
    return name


async def generate_article(
    ai_client: object,
    issue_data: dict,
    comments: list[dict] | None = None,
    model: str = "gpt-4o-mini",
) -> str | None:
    """Generate a KB article draft from issue data using AI.

    Returns the generated markdown content or None on failure.
    """
    prompt = load_prompt()

    issue_text = f"Issue #{issue_data.get('number', '?')}: {issue_data.get('title', '')}\n\n"
    issue_text += issue_data.get("body", "") or ""

    if comments:
        issue_text += "\n\n--- Comments ---\n"
        for comment in comments:
            author = comment.get("user", {}).get("login", "unknown")
            body = comment.get("body", "")
            issue_text += f"\n**{author}**: {body}\n"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": issue_text},
    ]

    try:
        response = await ai_client.chat.completions.create(  # type: ignore[union-attr]
            model=model,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=1000,
        )
        content = response.choices[0].message.content or ""

        if not validate_frontmatter(content):
            logger.warning("Generated article has invalid frontmatter")
            return None

        return content

    except Exception as e:
        logger.error("AI article generation failed: %s", e)
        return None


def write_draft(content: str, title: str) -> Path:
    """Write a draft KB article to the approved_answers directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"_draft_{sanitize_filename(title)}.md"
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    logger.info("Draft KB article written: %s", path)
    return path
