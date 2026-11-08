"""AI clients and cost tracker shared by the scheduled follow-up and the reply handler."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from model_choice import pick_model


async def make_ai_context(github_token: str, settings: dict[str, Any]) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "github_models_client": None,
        "openai_client": None,
        "cost_tracker": None,
        "openai_model": None,
    }
    try:
        from openai import AsyncOpenAI

        if github_token:
            ctx["github_models_client"] = AsyncOpenAI(base_url="https://models.github.ai/inference", api_key=github_token)
        if os.environ.get("OPENAI_API_KEY"):
            ctx["openai_client"] = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    except ImportError:
        pass
    from cost_tracker import tracker_from_settings

    cost_file = Path("/tmp/ai-cost-tracker/cost.json")
    cost_file.parent.mkdir(parents=True, exist_ok=True)
    choice = await pick_model(ctx["openai_client"], settings)
    ctx["openai_model"] = choice.id
    ctx["cost_tracker"] = tracker_from_settings(cost_file, settings, choice)
    return ctx
