"""AI clients and cost tracker shared by the scheduled follow-up and the reply handler."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def make_ai_context(github_token: str, budget_usd: float) -> dict[str, Any]:
    ctx: dict[str, Any] = {"github_models_client": None, "openai_client": None, "cost_tracker": None}
    try:
        from openai import AsyncOpenAI

        if github_token:
            ctx["github_models_client"] = AsyncOpenAI(base_url="https://models.inference.ai.azure.com", api_key=github_token)
        if os.environ.get("OPENAI_API_KEY"):
            ctx["openai_client"] = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    except ImportError:
        pass
    from cost_tracker import CostTracker

    cost_file = Path("/tmp/ai-cost-tracker/cost.json")
    cost_file.parent.mkdir(parents=True, exist_ok=True)
    ctx["cost_tracker"] = CostTracker(cost_file=cost_file, budget_usd=budget_usd)
    return ctx
