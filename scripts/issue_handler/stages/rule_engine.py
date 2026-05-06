"""Stage 1: Rule Engine — keyword matching (T026).

Matches issue title+body against configured keyword rules.
First match wins. References approved answer files from knowledge base.
"""

from __future__ import annotations

import logging
from typing import Any

from knowledge_base import KnowledgeBase
from models import PipelineDecision, WebhookEvent

logger = logging.getLogger(__name__)


async def rule_engine_stage(event: WebhookEvent, context: dict[str, Any]) -> PipelineDecision:
    """Check issue against keyword rules. First match wins."""
    rules = context.get("rules", [])
    kb_dir = context.get("kb_dir", "")

    if not rules:
        return PipelineDecision(
            stage="rule_engine", decision="pass", reason="no rules configured", short_circuit=False
        )

    text = (event.title + " " + event.body).lower()
    kb = KnowledgeBase(kb_dir)

    for rule in rules:
        name = rule.get("name", "unnamed")
        keywords = [kw.lower() for kw in rule.get("keywords", [])]
        match_mode = rule.get("match_mode", "any")

        if match_mode == "all":
            matched = all(kw in text for kw in keywords)
        else:
            matched = any(kw in text for kw in keywords)

        if matched:
            answer_file = rule.get("answer_file", "")
            answer = kb.get_answer_by_filename(answer_file)

            if answer is None:
                logger.warning("Rule '%s' references missing answer file: %s", name, answer_file)
                context["rule_match"] = {
                    "answer": "",
                    "labels": ["needs-triage"],
                    "close": False,
                }
                return PipelineDecision(
                    stage="rule_engine",
                    decision="match",
                    reason=f"rule '{name}' matched but answer file '{answer_file}' missing, needs-triage",
                    short_circuit=True,
                )

            context["rule_match"] = {
                "answer": answer.content,
                "labels": rule.get("labels", []),
                "close": rule.get("close", False),
            }
            return PipelineDecision(
                stage="rule_engine",
                decision="match",
                reason=f"rule '{name}' matched keyword(s) in issue text",
                short_circuit=True,
            )

    return PipelineDecision(
        stage="rule_engine", decision="pass", reason="no rule matched", short_circuit=False
    )
