"""Cascade pipeline orchestration (T011).

Runs stages sequentially. Each stage can short-circuit the pipeline.
Logs each decision as structured JSON to stdout (BR-005).
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from models import PipelineDecision, WebhookEvent

StageFunc = Callable[[WebhookEvent, dict[str, Any]], Awaitable[PipelineDecision]]

# Classification labels that indicate maintainer triage
CLASSIFICATION_LABELS = {"bug", "enhancement", "support", "needs-info"}


def should_skip_edited_event(event: WebhookEvent) -> bool:
    """Check if an edited event should be skipped (maintainer already labeled)."""
    if event.action != "edited":
        return False
    return bool(set(event.existing_labels) & CLASSIFICATION_LABELS)


class Pipeline:
    """Multi-stage cascade pipeline for issue processing."""

    def __init__(self) -> None:
        self._stages: list[tuple[str, StageFunc]] = []

    def add_stage(self, name: str, func: StageFunc) -> None:
        self._stages.append((name, func))

    async def run(self, event: WebhookEvent, context: dict[str, Any] | None = None) -> list[PipelineDecision]:
        """Execute all stages in order. Short-circuit on any stage that requests it."""
        if context is None:
            context = {}
        decisions: list[PipelineDecision] = []

        # Edit guard: skip if maintainer already applied classification label (T044)
        if should_skip_edited_event(event):
            decision = PipelineDecision(
                stage="edit_guard",
                decision="skip",
                reason="maintainer classification label already present",
                short_circuit=True,
            )
            decisions.append(decision)
            log_entry = {
                "stage": decision.stage,
                "decision": decision.decision,
                "reason": decision.reason,
                "short_circuit": decision.short_circuit,
            }
            print(json.dumps(log_entry), flush=True)
            return decisions

        for name, func in self._stages:
            decision = await func(event, context)
            decisions.append(decision)

            # Log decision as structured JSON (BR-005)
            log_entry = {
                "stage": decision.stage,
                "decision": decision.decision,
                "reason": decision.reason,
                "short_circuit": decision.short_circuit,
            }
            print(json.dumps(log_entry), flush=True)

            if decision.short_circuit:
                break

        return decisions
