"""Find sources for an answer: approved answers, docs and README chunks, and verified solved threads.

Only these sources may be used. A thread counts as a source only when it carries the label
`verified-solution` (set after the starter or the maintainer confirmed the solution).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bot_markers import SOLUTION_MARKER
from sanitizer import sanitize_input

VERIFIED_LABEL = "verified-solution"
_STOP = set(
    "the and for you your with that this have has not are was were but can how what why when from "
    "there their they them then than into out all any some more about would could should does did "
    "its it's i'm i've a an of to in on at is it be as or if so we my me".split()
)
_WORD = re.compile(r"[a-z0-9][a-z0-9._-]{2,}")


@dataclass
class Source:
    kind: str  # "kb" | "docs" | "thread"
    title: str
    url: str
    text: str
    relevance: float


def tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def relevance(query: set[str], doc: set[str]) -> float:
    """Share of the (capped) query terms that appear in the document; needs at least 3 shared terms."""
    if not query:
        return 0.0
    shared = len(query & doc)
    if shared < 3:
        return 0.0
    return min(1.0, shared / min(len(query), 15))


def _slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9 -]", "", heading.lower()).strip().replace(" ", "-")


def doc_chunks(repo_root: Path, repo_slug: str) -> list[tuple[str, str, str]]:
    """(title, url, text) per `## ` section of README.md and docs/*.md."""
    files = [repo_root / "README.md", *sorted((repo_root / "docs").glob("*.md"))]
    out: list[tuple[str, str, str]] = []
    for f in files:
        if not f.is_file():
            continue
        rel = f.relative_to(repo_root).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for part in re.split(r"(?m)^(?=## )", text):
            heading = part.splitlines()[0].lstrip("# ").strip() if part.startswith("## ") else f.stem
            anchor = f"#{_slug(heading)}" if part.startswith("## ") else ""
            out.append((f"{f.stem}: {heading}", f"https://github.com/{repo_slug}/blob/main/{rel}{anchor}", part))
    return out


async def _thread_sources(client: Any, query: set[str], repo_slug: str, min_relevance: float) -> list[Source]:
    found: list[Source] = []
    try:
        hits = await client.search_labelled_threads(VERIFIED_LABEL, sorted(query, key=len, reverse=True)[:8], limit=5)
    except Exception:  # search is best effort; no thread source is better than no answer at all
        return found
    for hit in hits[:3]:
        score = relevance(query, tokens(f"{hit.get('title', '')} {hit.get('body') or ''}"))
        if score < min_relevance:
            continue
        try:
            comments = await client.get_issue_comments(hit["number"])
        except Exception:  # one unreadable thread must not cost the whole answer
            continue
        marked = [c for c in comments if SOLUTION_MARKER in (c.get("body") or "")]
        author = (hit.get("user") or {}).get("login", "")
        others = [c for c in comments if (c.get("user") or {}).get("login") not in (author, "") and (c.get("user") or {}).get("type") != "Bot"]
        solution = (marked or others or [None])[-1]
        if solution is None:
            continue
        body = re.sub(r"<!--.*?-->", "", solution.get("body") or "", flags=re.S).strip()[:800]
        found.append(
            Source("thread", f"#{hit['number']} {hit.get('title', '')}", hit["html_url"],
                   f"Problem: {hit.get('title', '')}\nSolution: {body}", score)
        )
    return found


async def find_sources(
    client: Any,
    title: str,
    body: str,
    kb_answers: list[Any],
    repo_root: Path,
    repo_slug: str,
    min_relevance: float = 0.3,
    max_sources: int = 3,
) -> list[Source]:
    """Return up to `max_sources` sources whose relevance reaches `min_relevance`, best first."""
    query = tokens(sanitize_input(title, is_title=True) + " " + sanitize_input(body))
    sources: list[Source] = []
    for a in kb_answers:
        # Tag matches are loose (generic tags like "error"), so approved answers must pass the same relevance bar
        score = relevance(query, tokens(f"{a.title or ''} {a.content}"))
        if score >= min_relevance:
            url = f"https://github.com/{repo_slug}/blob/main/scripts/issue_handler/knowledge_base/approved_answers/{a.filename}"
            sources.append(Source("kb", a.title or a.filename, url, a.content, score))
    for chunk_title, url, text in doc_chunks(repo_root, repo_slug):
        score = relevance(query, tokens(text))
        if score >= min_relevance:
            sources.append(Source("docs", chunk_title, url, text[:1500], score))
    sources += await _thread_sources(client, query, repo_slug, min_relevance)
    sources.sort(key=lambda s: -s.relevance)
    return sources[:max_sources]
