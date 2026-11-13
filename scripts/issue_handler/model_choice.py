"""Pick the OpenAI fallback model: the first candidate of rules.yml that the API key can use.

The API lists the available model ids but no prices, so the candidates (cheapest first) carry their own
prices. Prices: https://developers.openai.com/api/docs/pricing (Flex tier).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelChoice:
    id: str
    input_usd_per_million: float
    output_usd_per_million: float


# Used when rules.yml has no `openai_models` list (Flex prices, checked 2026-11-08)
DEFAULT_CANDIDATES = [
    ModelChoice("gpt-5.4-nano", 0.10, 0.625),
]


def candidates(settings: dict[str, Any]) -> list[ModelChoice]:
    out = [
        ModelChoice(str(m["id"]), float(m["input_usd_per_million"]), float(m["output_usd_per_million"]))
        for m in settings.get("openai_models") or []
    ]
    return out or list(DEFAULT_CANDIDATES)


def _announce(message: str) -> None:
    """Make a model problem visible: warning in the log, JSON line and a note in the job summary."""
    logger.warning(message)
    print(json.dumps({"stage": "models", "warning": message}), flush=True)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"\n:warning: {message}\n")


async def pick_model(client: Any, settings: dict[str, Any]) -> ModelChoice:
    """First candidate the key can use. Without a client or when the listing fails, the first candidate."""
    options = candidates(settings)
    if client is None:
        return options[0]
    try:
        page = await client.models.list()
        available = {m.id for m in page.data}
    except Exception as e:  # listing is a convenience; an unreachable API must not stop the handler
        logger.warning("Could not list OpenAI models (%s), using %s", e, options[0].id)
        return options[0]
    missing = [o.id for o in options if o.id not in available]
    if missing:
        _announce(f"Configured in rules.yml but not available for this API key (remove or update them): {', '.join(missing)}")
    for option in options:
        if option.id in available:
            return option
    _announce(f"None of the configured OpenAI models is available, using {options[0].id} anyway")
    return options[0]
