"""Stage 0: Hard Exit — skip owner/maintainer/bot (T016).

Checks author_association, sender_type, and bot_username.
Short-circuits the pipeline for privileged users and bots.
"""

from __future__ import annotations

from typing import Any

from models import PipelineDecision, WebhookEvent

SKIP_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


async def hard_exit_stage(event: WebhookEvent, context: dict[str, Any]) -> PipelineDecision:
    """Check if event should be skipped based on sender identity."""
    # Check author association
    if event.author_association in SKIP_ASSOCIATIONS:
        return PipelineDecision(
            stage="hard_exit",
            decision="skip",
            reason=f"sender is {event.author_association}",
            short_circuit=True,
        )

    # Check if sender is a bot
    if event.sender_type == "Bot":
        return PipelineDecision(
            stage="hard_exit",
            decision="skip",
            reason=f"sender type is Bot ({event.sender_login})",
            short_circuit=True,
        )

    # Check explicit bot username
    bot_username = context.get("bot_username", "")
    if bot_username and event.sender_login == bot_username:
        return PipelineDecision(
            stage="hard_exit",
            decision="skip",
            reason=f"sender is configured bot account ({bot_username})",
            short_circuit=True,
        )

    return PipelineDecision(
        stage="hard_exit",
        decision="pass",
        reason=f"sender is community user ({event.author_association})",
        short_circuit=False,
    )
