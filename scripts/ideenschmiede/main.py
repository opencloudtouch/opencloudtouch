"""Ideenschmiede automation: seed discussions from idea files, refresh the sticky overview issue.

Usage:  python scripts/ideenschmiede/main.py {seed|sticky|both} [--dry-run]
Env:    GH_TOKEN, GITHUB_REPOSITORY (owner/name). Requires the `gh` CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ideas import (
    STICKY_MARKER,
    Idea,
    discussion_body,
    idea_id_from_body,
    load_ideas,
    render_sticky,
)

CATEGORY_SLUG = "ideenschmiede"
STICKY_LABEL = "ideenschmiede"
IDEAS_DIR = Path(__file__).resolve().parents[2] / "docs" / "ideenschmiede" / "ideas"
LABELS = {
    STICKY_LABEL: ("5319e7", "Self-updating Ideenschmiede overview"),
    "idea:accepted": ("0e8a16", "Idea will be pursued; a spec follows"),
    "idea:specced": ("1d76db", "A spec issue exists for this idea"),
    "idea:declined": ("b60205", "Idea was decided against"),
}

DISCUSSIONS_QUERY = """
query($owner: String!, $name: String!, $category: ID!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 50, after: $after, categoryId: $category) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url body upvoteCount
        author { login }
        comments { totalCount }
        labels(first: 20) { nodes { name } }
        reactionGroups { content reactors { totalCount } }
      }
    }
  }
}
"""


class GhError(RuntimeError):
    pass


def gh(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()[:500]}")
    return result.stdout


def graphql(query: str, **variables: object) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    return json.loads(gh(*args))["data"]


def find_category(owner: str, name: str) -> tuple[str, str]:
    """Return (repository node id, category node id); raise if the category is missing."""
    data = graphql(
        "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id "
        "discussionCategories(first:50){nodes{id slug}}}}",
        owner=owner,
        name=name,
    )["repository"]
    for node in data["discussionCategories"]["nodes"]:
        if node["slug"] == CATEGORY_SLUG:
            return data["id"], node["id"]
    raise GhError(
        f"Discussion category '{CATEGORY_SLUG}' does not exist. "
        "Create it once in Settings > Discussions (format: open-ended discussion), then run again."
    )


def fetch_discussions(owner: str, name: str, category_id: str) -> list[dict]:
    rows: list[dict] = []
    after = None
    while True:
        page = graphql(DISCUSSIONS_QUERY, owner=owner, name=name, category=category_id, after=after)
        block = page["repository"]["discussions"]
        for node in block["nodes"]:
            reactions = {g["content"]: g["reactors"]["totalCount"] for g in node["reactionGroups"]}
            rows.append(
                {
                    "number": node["number"],
                    "title": node["title"],
                    "url": node["url"],
                    "body": node["body"],
                    "upvotes": node["upvoteCount"] + reactions.get("THUMBS_UP", 0),
                    "downvotes": reactions.get("THUMBS_DOWN", 0),
                    "comments": node["comments"]["totalCount"],
                    "labels": [label["name"] for label in node["labels"]["nodes"]],
                    "author": (node["author"] or {}).get("login", "ghost"),
                }
            )
        if not block["pageInfo"]["hasNextPage"]:
            return rows
        after = block["pageInfo"]["endCursor"]


def missing_ideas(ideas: list[Idea], discussions: list[dict]) -> list[Idea]:
    seeded = {idea_id_from_body(d["body"]) for d in discussions}
    return [idea for idea in ideas if idea.id not in seeded]


def ensure_labels(repo: str, dry_run: bool) -> None:
    for name, (color, description) in LABELS.items():
        if dry_run:
            print(f"[dry-run] ensure label {name}")
            continue
        try:
            gh(
                "api",
                f"repos/{repo}/labels",
                "-f",
                f"name={name}",
                "-f",
                f"color={color}",
                "-f",
                f"description={description}",
            )
        except GhError as exc:
            if "already_exists" not in str(exc) and "Validation Failed" not in str(exc):
                raise


def seed(repo: str, dry_run: bool) -> None:
    owner, name = repo.split("/")
    repo_id, category_id = find_category(owner, name)
    ensure_labels(repo, dry_run)
    todo = missing_ideas(load_ideas(IDEAS_DIR), fetch_discussions(owner, name, category_id))
    if not todo:
        print("seed: every idea already has a discussion")
    for idea in todo:
        if dry_run:
            print(f"[dry-run] would create discussion '{idea.title}' (idea {idea.id})")
            continue
        data = graphql(
            "mutation($r:ID!,$c:ID!,$t:String!,$b:String!){createDiscussion(input:"
            "{repositoryId:$r,categoryId:$c,title:$t,body:$b}){discussion{url}}}",
            r=repo_id,
            c=category_id,
            t=idea.title,
            b=discussion_body(idea, repo),
        )
        print(f"seed: created {data['createDiscussion']['discussion']['url']}")


def sticky(repo: str, dry_run: bool) -> None:
    owner, name = repo.split("/")
    _repo_id, category_id = find_category(owner, name)
    body = render_sticky(
        fetch_discussions(owner, name, category_id),
        repo=repo,
        generated=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    if dry_run:
        print(body)
        return
    existing = json.loads(gh("api", f"repos/{repo}/issues?labels={STICKY_LABEL}&state=open&per_page=100"))
    issue = next((i for i in existing if STICKY_MARKER in (i.get("body") or "") and "pull_request" not in i), None)
    if issue is None:
        ensure_labels(repo, dry_run=False)
        payload = json.dumps({"title": "Ideenschmiede", "body": body, "labels": [STICKY_LABEL]})
        issue = json.loads(gh("api", f"repos/{repo}/issues", "--input", "-", stdin=payload))
        print(f"sticky: created #{issue['number']}")
    elif issue["body"] != body.replace("\r\n", "\n") and _strip_stamp(issue["body"]) != _strip_stamp(body):
        gh(
            "api",
            "-X",
            "PATCH",
            f"repos/{repo}/issues/{issue['number']}",
            "--input",
            "-",
            stdin=json.dumps({"body": body}),
        )
        print(f"sticky: updated #{issue['number']}")
    else:
        print(f"sticky: #{issue['number']} unchanged")
    try:  # pinning is best effort: needs permissions the default token may lack
        graphql("mutation($i:ID!){pinIssue(input:{issueId:$i}){issue{number}}}", i=issue["node_id"])
    except GhError as exc:
        print(f"sticky: not pinned ({exc})")


def _strip_stamp(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.startswith("_Last updated"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "sticky", "both"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        print("GITHUB_REPOSITORY must be set to owner/name", file=sys.stderr)
        return 2
    try:
        if args.action in ("seed", "both"):
            seed(repo, args.dry_run)
        if args.action in ("sticky", "both"):
            sticky(repo, args.dry_run)
    except GhError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
