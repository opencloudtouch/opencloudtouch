"""Cost tracker for the OpenAI calls (T040).

Tracks monthly AI API costs via a JSON file persisted through GitHub Actions Cache. Only OpenAI calls
are counted (GitHub Models was retired on 2026-07-30). Model and prices are settings in rules.yml; the defaults
are the Flex prices of gpt-5.4-nano from https://developers.openai.com/api/docs/pricing (checked 2026-11-08).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import CostRecord

DEFAULT_INPUT_USD_PER_MILLION = 0.10   # gpt-5.4-nano, Flex
DEFAULT_OUTPUT_USD_PER_MILLION = 0.625


class CostTracker:
    """Track monthly AI API costs."""

    def __init__(
        self,
        cost_file: Path,
        budget_usd: float = 0.90,
        input_usd_per_million: float = DEFAULT_INPUT_USD_PER_MILLION,
        output_usd_per_million: float = DEFAULT_OUTPUT_USD_PER_MILLION,
    ) -> None:
        self._cost_file = cost_file
        self._budget_usd = budget_usd
        self._input_per_token = input_usd_per_million / 1_000_000
        self._output_per_token = output_usd_per_million / 1_000_000
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
        cost = (input_tokens * self._input_per_token) + (output_tokens * self._output_per_token)
        self._record.total_cost_usd += cost
        self._record.call_count += 1

    def use_prices(self, input_usd_per_million: float, output_usd_per_million: float) -> None:
        """Switch to the prices of the model that was chosen after the tracker was created."""
        self._input_per_token = input_usd_per_million / 1_000_000
        self._output_per_token = output_usd_per_million / 1_000_000

    def is_budget_exceeded(self) -> bool:
        """Check if monthly budget has been exceeded."""
        return self._record.total_cost_usd >= self._budget_usd

    def summary_line(self) -> str:
        return (
            f"AI cost this month ({self._month}, OpenAI calls only): "
            f"${self.total_cost_usd:.4f} of ${self._budget_usd:.2f} budget, {self.call_count} calls"
        )


def tracker_from_settings(cost_file: Path, settings: dict, choice: Any = None) -> CostTracker:
    """Build the tracker with the budget from rules.yml and the prices of the chosen model."""
    return CostTracker(
        cost_file=cost_file,
        budget_usd=settings.get("monthly_budget_usd", 0.90),
        input_usd_per_million=choice.input_usd_per_million if choice else DEFAULT_INPUT_USD_PER_MILLION,
        output_usd_per_million=choice.output_usd_per_million if choice else DEFAULT_OUTPUT_USD_PER_MILLION,
    )


def report_cost(tracker: "CostTracker | None") -> None:
    """Log the cost state and add it to the job summary, so the budget is visible after every run."""
    if tracker is None:
        return
    line = tracker.summary_line()
    print(json.dumps({"stage": "cost", "summary": line}), flush=True)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"\n{line}\n")
