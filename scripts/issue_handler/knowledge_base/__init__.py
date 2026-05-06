"""Knowledge Base loader for approved answers (T024).

Loads Markdown files with YAML Frontmatter from the approved_answers directory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

logger = logging.getLogger(__name__)


@dataclass
class ApprovedAnswer:
    """A curated answer template from the knowledge base."""

    filename: str
    tags: list[str] = field(default_factory=list)
    content: str = ""
    title: str = ""


class KnowledgeBase:
    """Loads and manages approved answer files."""

    def __init__(self, answers_dir: Path | str) -> None:
        self._answers_dir = Path(answers_dir)
        self._answers: list[ApprovedAnswer] | None = None

    def get_all_answers(self) -> list[ApprovedAnswer]:
        """Load all approved answer files from the knowledge base directory."""
        if self._answers is not None:
            return self._answers

        self._answers = []

        if not self._answers_dir.exists() or not self._answers_dir.is_dir():
            return self._answers

        for md_file in sorted(self._answers_dir.glob("*.md")):
            try:
                post = frontmatter.load(str(md_file))
                tags = post.metadata.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]
                content = post.content

                # Extract title from first heading
                title = ""
                for line in content.splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

                self._answers.append(
                    ApprovedAnswer(
                        filename=md_file.name,
                        tags=tags,
                        content=content,
                        title=title,
                    )
                )
            except Exception as e:
                logger.warning("Failed to load %s: %s", md_file.name, e)

        return self._answers

    def get_answer_by_filename(self, filename: str) -> ApprovedAnswer | None:
        """Get a specific approved answer by filename."""
        for answer in self.get_all_answers():
            if answer.filename == filename:
                return answer
        return None

    def select_relevant_answers(
        self, title: str, body: str, max_results: int = 5
    ) -> list[ApprovedAnswer]:
        """Select the most relevant answers based on tag matching (T031).

        Tokenizes title+body into lowercase words, counts tag intersections,
        and returns top N results sorted by match count then filename.
        """
        text = (title + " " + body).lower()
        words = set(text.split())

        scored: list[tuple[int, str, ApprovedAnswer]] = []
        for answer in self.get_all_answers():
            match_count = sum(1 for tag in answer.tags if tag.lower() in words)
            if match_count > 0:
                scored.append((match_count, answer.filename, answer))

        # Sort by match count descending, then filename ascending
        scored.sort(key=lambda x: (-x[0], x[1]))

        return [item[2] for item in scored[:max_results]]
