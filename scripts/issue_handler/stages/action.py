"""Stage 5: Action — apply labels, post comments, close (T020).

Handles both rule-match actions and AI classification actions.
"""

from __future__ import annotations

from typing import Any

from models import ClassificationResult, PipelineDecision, WebhookEvent

LABEL_MAP = {
    "bug": "bug",
    "feature": "enhancement",
    "support": "support",
    "unclear": "needs-info",
}

CONFIDENCE_THRESHOLD = 0.7

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
    """Handle AI classification: apply label, post comments based on category."""
    label = LABEL_MAP.get(classification.category, "needs-triage")
    is_discussion = event.is_discussion if event is not None else False

    # Skip labels for discussions (no label API available)
    if not is_discussion:
        await github_client.add_labels(issue_number, [label])

        # Low confidence → add needs-triage (except for 'unclear' per FR-018)
        if classification.confidence < CONFIDENCE_THRESHOLD and classification.category != "unclear":
            await github_client.add_labels(issue_number, ["needs-triage"])

    # Category-specific actions
    if classification.category == "bug" and not classification.is_clear_bug:
        if event is None or not event.is_discussion:
            await github_client.post_comment(issue_number, BUG_TEMPLATE_COMMENT)

    elif classification.category == "support":
        support_comment = context.get("support_comment", "")
        if support_comment:
            await github_client.post_comment(issue_number, support_comment)

    elif classification.category == "unclear":
        follow_up = context.get("follow_up_questions", "")
        if follow_up:
            await github_client.post_comment(issue_number, follow_up)

    return PipelineDecision(
        stage="action",
        decision="act",
        reason=f"applied label '{label}', category={classification.category}, confidence={classification.confidence}",
        short_circuit=True,
    )
