"""Data models for the AI Issue Handler pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WebhookEvent:
    """Represents an incoming GitHub event parsed from GITHUB_EVENT_PATH."""

    event_type: str
    action: str
    sender_login: str
    sender_type: str
    author_association: str
    repo_owner: str
    repo_name: str
    issue_number: int | None
    title: str
    body: str
    existing_labels: list[str] = field(default_factory=list)
    is_discussion: bool = False

    @classmethod
    def from_payload(cls, event_type: str, payload: dict[str, Any]) -> WebhookEvent:
        """Parse a GitHub webhook event payload into a WebhookEvent."""
        action = payload.get("action", "")
        sender = payload.get("sender", {})
        repo = payload.get("repository", {})

        is_discussion = event_type == "discussion"

        if is_discussion:
            item = payload.get("discussion", {})
            author_association = item.get("author_association", "NONE")
            labels: list[str] = []
        elif event_type == "issue_comment":
            item = payload.get("issue", {})
            comment = payload.get("comment", {})
            author_association = comment.get("author_association", item.get("author_association", "NONE"))
            labels = [lbl["name"] for lbl in item.get("labels", [])]
        else:
            item = payload.get("issue", {})
            author_association = item.get("author_association", "NONE")
            labels = [lbl["name"] for lbl in item.get("labels", [])]

        # Merge parent issue body + comment body for classification context (T048)
        if event_type == "issue_comment":
            comment = payload.get("comment", {})
            parent_body = item.get("body") or ""
            comment_body = comment.get("body") or ""
            body = (parent_body + "\n\n" + comment_body).strip() if comment_body else parent_body
        else:
            body = item.get("body") or ""

        return cls(
            event_type=event_type,
            action=action,
            sender_login=sender.get("login", ""),
            sender_type=sender.get("type", "User"),
            author_association=author_association,
            repo_owner=repo.get("owner", {}).get("login", ""),
            repo_name=repo.get("name", ""),
            issue_number=item.get("number"),
            title=item.get("title", ""),
            body=body,
            existing_labels=labels,
            is_discussion=is_discussion,
        )


@dataclass
class ClassificationResult:
    """Output of the AI classification stage."""

    category: str
    confidence: float
    reasoning: str
    is_clear_bug: bool = False
    kb_match: str | None = None
    is_on_topic: bool = True


@dataclass
class PipelineDecision:
    """Log entry for each pipeline stage decision."""

    stage: str
    decision: str
    reason: str
    short_circuit: bool = False


@dataclass
class CostRecord:
    """Tracks monthly AI cost for OpenAI fallback."""

    month: str
    total_cost_usd: float = 0.0
    call_count: int = 0
    last_updated: str = ""
