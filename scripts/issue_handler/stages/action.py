"""Stage 5: Action — apply labels, post comments, close (T020).

Handles both rule-match actions and AI classification actions.
Three-signal guarantee: every processed issue gets label + assignee + comment.
"""

from __future__ import annotations

import logging
from typing import Any

from models import ClassificationResult, PipelineDecision, WebhookEvent

logger = logging.getLogger(__name__)

LABEL_MAP = {
    "bug": "bug",
    "feature": "enhancement",
    "support": "support",
    "unclear": "needs-info",
    "off-topic": "off-topic",
    "spam": "spam",
}

CONFIDENCE_THRESHOLD = 0.7
MAX_SIGNAL_RETRIES = 3

BUG_TEMPLATE_COMMENT = (
    "Thank you for reporting this issue! 🐛\n\n"
    "To help us investigate, could you please provide more details using our "
    "[bug report template](../../.github/ISSUE_TEMPLATE/bug_report.yml)?\n\n"
    "Specifically, we need:\n"
    "1. Steps to reproduce the issue\n"
    "2. Expected vs actual behavior\n"
    "3. Your environment (device model, OS, browser)\n\n"
    "This will help us resolve the issue faster. Thanks!"
)

# Fields to check in bug reports — header text → human-readable name
_BUG_REQUIRED_FIELDS: list[tuple[str, str]] = [
    ("### Steps to Reproduce", "Steps to reproduce"),
    ("### Backend Logs", "Backend logs (`docker logs opencloudtouch`)"),
    ("### OpenCloudTouch Version", "OpenCloudTouch version"),
]

_PLACEHOLDER_MARKERS = {"_no response_", "```shell\n\n```", "```shell\r\n\r\n```"}


def _find_missing_bug_fields(body: str) -> list[str]:
    """Check which required bug report fields are empty or missing."""
    missing: list[str] = []
    body_lower = body.lower()
    for header, label in _BUG_REQUIRED_FIELDS:
        header_lower = header.lower()
        idx = body_lower.find(header_lower)
        if idx == -1:
            missing.append(label)
            continue
        # Extract content between this header and the next ### or end
        after = body[idx + len(header):]
        next_header = after.find("\n### ")
        section = after[:next_header].strip() if next_header != -1 else after.strip()
        # Check if section is empty or just placeholder
        if not section or section.lower() in _PLACEHOLDER_MARKERS:
            missing.append(label)
    return missing


def _build_bug_comment(body: str) -> str:
    """Build a targeted bug comment based on which fields are missing."""
    missing = _find_missing_bug_fields(body)
    if not missing:
        # All fields filled — treat as clear bug report
        return BUG_CLEAR_TEMPLATE
    items = "\n".join(f"- {field}" for field in missing)
    return (
        "Thank you for reporting this issue! 🐛\n\n"
        "To help us investigate, could you please add the following missing details?\n\n"
        f"{items}\n\n"
        "This will help us resolve the issue faster. Thanks!"
    )


BUG_CLEAR_TEMPLATE = (
    "Thank you for the detailed bug report! 🐛\n\n"
    "We've labeled this as a **bug** and it's on our radar. A maintainer will investigate "
    "and follow up here.\n\n"
    "In the meantime, please make sure you're running the "
    "[latest version](https://github.com/opencloudtouch/opencloudtouch/releases/latest)."
)

FEATURE_TEMPLATE = (
    "Thank you for the feature suggestion! 💡\n\n"
    "We've noted this as an **enhancement** request. The maintainer will review it and "
    "decide on prioritization.\n\n"
    "You can check our [existing issues](https://github.com/opencloudtouch/opencloudtouch/issues?q=is%3Aissue+label%3Aenhancement) "
    "to see if a similar feature has been discussed before."
)

OFF_TOPIC_TEMPLATE = (
    "Thank you for reaching out! 👋\n\n"
    "This issue doesn't appear to be related to **OpenCloudTouch** (a bridge between "
    "Bose SoundTouch speakers and smart home systems).\n\n"
    "If you believe this is a mistake, please update your issue with more context about "
    "how it relates to OpenCloudTouch. Otherwise, a maintainer will review this shortly."
)

SPAM_TEMPLATE = "This issue has been flagged for review by a maintainer."


async def _safe_call(coro_fn: Any, *args: Any, retries: int = MAX_SIGNAL_RETRIES) -> bool:
    """Execute an async call with retries. Returns True on success, False on failure."""
    for attempt in range(retries):
        try:
            await coro_fn(*args)
            return True
        except Exception as e:
            logger.warning("Signal failed (attempt %d/%d): %s", attempt + 1, retries, e)
    return False


async def action_stage(event: WebhookEvent, context: dict[str, Any]) -> PipelineDecision:
    """Apply labels, post comments, and optionally close based on classification or rule match."""
    github_client = context.get("github_client")
    if github_client is None:
        return PipelineDecision(stage="action", decision="skip", reason="no github client", short_circuit=True)

    issue_number = event.issue_number
    if issue_number is None:
        return PipelineDecision(stage="action", decision="skip", reason="no issue number", short_circuit=True)

    # Handle rule match (from Stage 1)
    rule_match = context.get("rule_match")
    if rule_match:
        return await _handle_rule_match(github_client, issue_number, rule_match)

    # Handle AI classification (from Stage 4)
    classification = context.get("classification")
    if classification:
        return await _handle_classification(github_client, issue_number, classification, context, event)

    return PipelineDecision(stage="action", decision="skip", reason="no classification or rule match", short_circuit=True)


async def _handle_rule_match(
    github_client: Any, issue_number: int, rule_match: dict[str, Any]
) -> PipelineDecision:
    """Handle rule engine match: post answer, apply labels, optionally close."""
    labels = rule_match.get("labels", [])
    if labels:
        await github_client.add_labels(issue_number, labels)

    answer = rule_match.get("answer", "")
    if answer:
        await github_client.post_comment(issue_number, answer)

    if rule_match.get("close", False):
        await github_client.close_issue(issue_number)

    return PipelineDecision(
        stage="action",
        decision="act",
        reason=f"rule match: labels={labels}, close={rule_match.get('close', False)}",
        short_circuit=True,
    )


async def _handle_classification(
    github_client: Any,
    issue_number: int,
    classification: ClassificationResult,
    context: dict[str, Any],
    event: WebhookEvent | None = None,
) -> PipelineDecision:
    """Handle AI classification with 3-signal guarantee: label + assignee + comment."""
    is_discussion = event.is_discussion if event is not None else False
    bot_username = context.get("bot_username", "oct-support")
    any_failed = False

    # --- Signal 1: Labels ---
    label = LABEL_MAP.get(classification.category, "needs-triage")

    if not is_discussion:
        # Off-topic with low confidence → needs-triage instead
        if classification.category == "off-topic" and not classification.is_on_topic and classification.confidence < CONFIDENCE_THRESHOLD:
            label = "needs-triage"

        if not await _safe_call(github_client.add_labels, issue_number, [label]):
            any_failed = True

        # Low confidence → add needs-triage (except for 'unclear' and 'off-topic' per FR-018)
        if (
            classification.confidence < CONFIDENCE_THRESHOLD
            and classification.category not in ("unclear", "off-topic", "spam")
        ):
            await _safe_call(github_client.add_labels, issue_number, ["needs-triage"])

    # --- Signal 2: Assignee ---
    if not is_discussion:
        if not await _safe_call(github_client.set_assignee, issue_number, bot_username):
            any_failed = True
            await _safe_call(github_client.add_labels, issue_number, ["needs-triage"])

    # --- Signal 3: Comment ---
    comment = _select_comment(classification, context, event)
    if comment:
        if not await _safe_call(github_client.post_comment, issue_number, comment):
            any_failed = True

    # Fallback: if any signal completely failed, ensure needs-triage is set
    if any_failed and not is_discussion:
        await _safe_call(github_client.add_labels, issue_number, ["needs-triage"])

    return PipelineDecision(
        stage="action",
        decision="act",
        reason=f"applied label '{label}', category={classification.category}, confidence={classification.confidence}",
        short_circuit=True,
    )


def _select_comment(
    classification: ClassificationResult,
    context: dict[str, Any],
    event: WebhookEvent | None = None,
) -> str:
    """Select the appropriate comment for a classification category."""
    if classification.category == "bug":
        # Use body-aware field check instead of AI's is_clear_bug flag
        if event is not None and event.body:
            return _build_bug_comment(event.body)
        if classification.is_clear_bug:
            return BUG_CLEAR_TEMPLATE
        return BUG_TEMPLATE_COMMENT

    if classification.category == "feature":
        return FEATURE_TEMPLATE

    if classification.category == "support":
        # KB match → approved answer
        kb_match = classification.kb_match
        if kb_match:
            kb_answers = context.get("kb_answers", [])
            for answer in kb_answers:
                if answer.filename == kb_match:
                    return answer.content
        # AI-generated response
        return context.get("support_comment", "")

    if classification.category == "unclear":
        return context.get("follow_up_questions", "")

    if classification.category == "off-topic":
        return OFF_TOPIC_TEMPLATE

    if classification.category == "spam":
        return SPAM_TEMPLATE

    return ""
