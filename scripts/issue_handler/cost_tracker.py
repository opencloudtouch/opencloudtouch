"""Cost tracker for OpenAI fallback (T040).

Tracks monthly AI API costs via a JSON file persisted through GitHub Actions Cache.
GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output tokens.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models import CostRecord

# GPT-4o-mini pricing per token
INPUT_COST_PER_TOKEN = 0.15 / 1_000_000   # $0.15 per 1M input tokens
OUTPUT_COST_PER_TOKEN = 0.60 / 1_000_000  # $0.60 per 1M output tokens


class CostTracker:
    """Track monthly AI API costs."""

    def __init__(self, cost_file: Path, budget_usd: float = 0.90) -> None:
        self._cost_file = cost_file
        self._budget_usd = budget_usd
        self._month: str = datetime.now(timezone.utc).strftime("%Y-%m")
        self._record = CostRecord(month=self._month)
        self._load()

    @property
    def total_cost_usd(self) -> float:
        return self._record.total_cost_usd

    @property
    def call_count(self) -> int:
        return self._record.call_count

    def _load(self) -> None:
        """Load cost record from file, reset if different month."""
        if not self._cost_file.exists():
            return

        try:
            data = json.loads(self._cost_file.read_text())
            if data.get("month") == self._month:
                self._record.total_cost_usd = data.get("total_cost_usd", 0.0)
                self._record.call_count = data.get("call_count", 0)
                self._record.last_updated = data.get("last_updated", "")
            # else: different month → start fresh (already initialized to 0)
        except (json.JSONDecodeError, KeyError):
            pass

    def save(self) -> None:
        """Save cost record to file."""
        self._cost_file.parent.mkdir(parents=True, exist_ok=True)
        self._record.last_updated = datetime.now(timezone.utc).isoformat()
        data = {
            "month": self._record.month,
            "total_cost_usd": self._record.total_cost_usd,
            "call_count": self._record.call_count,
            "last_updated": self._record.last_updated,
        }
        self._cost_file.write_text(json.dumps(data, indent=2))

    def record_call(self, input_tokens: int, output_tokens: int) -> None:
        """Record a single AI API call cost."""
        cost = (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)
        self._record.total_cost_usd += cost
        self._record.call_count += 1

    def is_budget_exceeded(self) -> bool:
        """Check if monthly budget has been exceeded."""
        return self._record.total_cost_usd >= self._budget_usd
