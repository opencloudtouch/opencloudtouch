"""Tests for cost tracker (T039)."""

from __future__ import annotations

import json
from pathlib import Path

from cost_tracker import CostTracker


class TestCostTracker:
    def test_load_empty_creates_fresh(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json", budget_usd=0.90)
        assert tracker.total_cost_usd == 0.0
        assert tracker.call_count == 0

    def test_record_call_updates_cost(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json", budget_usd=0.90)
        tracker.record_call(input_tokens=1000, output_tokens=200)
        assert tracker.total_cost_usd > 0
        assert tracker.call_count == 1

    def test_budget_exceeded(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        # Pre-populate with high cost
        cost_file.write_text(json.dumps({
            "month": "2026-05",
            "total_cost_usd": 0.95,
            "call_count": 100,
            "last_updated": "2026-05-06T00:00:00",
        }))
        tracker = CostTracker(cost_file, budget_usd=0.90)
        assert tracker.is_budget_exceeded() is True

    def test_budget_not_exceeded(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json", budget_usd=0.90)
        assert tracker.is_budget_exceeded() is False

    def test_save_and_reload(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        tracker = CostTracker(cost_file, budget_usd=0.90)
        tracker.record_call(input_tokens=500, output_tokens=100)
        tracker.save()

        tracker2 = CostTracker(cost_file, budget_usd=0.90)
        assert tracker2.total_cost_usd == tracker.total_cost_usd
        assert tracker2.call_count == 1

    def test_month_rollover(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        cost_file.write_text(json.dumps({
            "month": "2026-04",
            "total_cost_usd": 0.50,
            "call_count": 50,
            "last_updated": "2026-04-30T00:00:00",
        }))
        tracker = CostTracker(cost_file, budget_usd=0.90)
        # Current month is 2026-05, old data should be reset
        assert tracker.total_cost_usd == 0.0
        assert tracker.call_count == 0
