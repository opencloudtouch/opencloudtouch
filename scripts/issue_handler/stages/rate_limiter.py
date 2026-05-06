"""Stage 2: Rate Limiter — per-user rate limiting (T036).

Queries GitHub Search API to count recent issues by the same author.
Stateless — no persistent storage needed.
"""

from __future__ import annotations

from typing import Any

from models import PipelineDecision, WebhookEvent

DEFAULT_RATE_LIMIT_THRESHOLD = 2

RATE_LIMIT_MESSAGE = (
    "Hi @{username},\n\n"
    "You've opened {count} issues in the last 24 hours, which exceeds our "
    "threshold of {threshold}. To ensure quality support for everyone, please "
    "wait before opening additional issues.\n\n"
    "If your issue is urgent, please update an existing issue instead of creating a new one.\n\n"
    "Thank you for your understanding! 🙏"
)


async def rate_limiter_stage(event: WebhookEvent, context: dict[str, Any]) -> PipelineDecision:
    """Check if user has exceeded the issue creation rate limit."""
    github_client = context.get("github_client")
    if github_client is None:
        return PipelineDecision(
            stage="rate_limiter", decision="pass", reason="no github client", short_circuit=False
        )

    threshold = context.get("rate_limit_threshold", DEFAULT_RATE_LIMIT_THRESHOLD)
    count = await github_client.search_issues_by_author(event.sender_login)

    if count >= threshold:
        message = RATE_LIMIT_MESSAGE.format(
            username=event.sender_login, count=count, threshold=threshold
        )
        context["rate_limit_message"] = message

        # Post rate limit message directly (action stage won't run due to short-circuit)
        if event.issue_number is not None:
            await github_client.post_comment(event.issue_number, message)

        return PipelineDecision(
            stage="rate_limiter",
            decision="block",
            reason=f"user {event.sender_login} has {count} issues in 24h (threshold: {threshold})",
            short_circuit=True,
        )

    return PipelineDecision(
        stage="rate_limiter",
        decision="pass",
        reason=f"user has {count} issues in 24h (threshold: {threshold})",
        short_circuit=False,
    )
