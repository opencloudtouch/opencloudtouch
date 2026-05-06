"""Stage 3: Heuristic Check — minimum text length (T018).

Checks if combined title+body has enough text for meaningful classification.
"""

from __future__ import annotations

from typing import Any

from models import PipelineDecision, WebhookEvent

DEFAULT_MIN_TEXT_LENGTH = 50


async def heuristic_stage(event: WebhookEvent, context: dict[str, Any]) -> PipelineDecision:
    """Check if issue text meets minimum length for AI classification."""
    min_length = context.get("min_text_length", DEFAULT_MIN_TEXT_LENGTH)
    text_length = len(event.title + event.body)

    if text_length < min_length:
        # Apply needs-info label directly (action stage won't run due to short-circuit)
        github_client = context.get("github_client")
        if github_client and event.issue_number is not None and not event.is_discussion:
            await github_client.add_labels(event.issue_number, ["needs-info"])

        return PipelineDecision(
            stage="heuristic",
            decision="block",
            reason=f"text length {text_length} < {min_length}, applying needs-info",
            short_circuit=True,
        )

    return PipelineDecision(
        stage="heuristic",
        decision="pass",
        reason=f"text length {text_length} >= {min_length}",
        short_circuit=False,
    )
