"""Tests for cost tracker (T039)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
        # Pre-populate with high cost for the current month (the tracker ignores other months)
        cost_file.write_text(json.dumps({
            "month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "total_cost_usd": 0.95,
            "call_count": 100,
            "last_updated": "2026-05-06T00:00:00",
        }))
        tracker = CostTracker(cost_file, budget_usd=0.90)
        assert tracker.is_budget_exceeded() is True

    def test_new_month_resets_the_counter(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        cost_file.write_text(json.dumps({
            "month": "2000-01",
            "total_cost_usd": 0.95,
            "call_count": 100,
            "last_updated": "2000-01-06T00:00:00",
        }))
        tracker = CostTracker(cost_file, budget_usd=0.90)
        assert tracker.total_cost_usd == 0
        assert tracker.is_budget_exceeded() is False

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


class TestPricesAndVisibility:
    def test_prices_come_from_the_chosen_model(self, tmp_path: Path) -> None:
        from cost_tracker import tracker_from_settings
        from model_choice import ModelChoice

        tracker = tracker_from_settings(tmp_path / "c.json", {}, ModelChoice("m", 2.0, 10.0))
        tracker.record_call(input_tokens=1_000_000, output_tokens=100_000)
        assert tracker.total_cost_usd == pytest.approx(3.0)

    def test_default_prices_are_the_flex_prices_of_the_default_model(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "c.json")
        tracker.record_call(input_tokens=1_000_000, output_tokens=1_000_000)
        assert tracker.total_cost_usd == pytest.approx(0.10 + 0.625)

    def test_use_prices_switches_to_the_chosen_model(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "c.json")
        tracker.use_prices(1.0, 5.0)
        tracker.record_call(input_tokens=1_000_000, output_tokens=1_000_000)
        assert tracker.total_cost_usd == pytest.approx(6.0)

    def test_rules_yml_lists_priced_candidates(self) -> None:
        import yaml

        from model_choice import candidates

        settings = yaml.safe_load((Path(__file__).parent.parent / "rules.yml").read_text(encoding="utf-8"))["settings"]
        options = candidates(settings)
        assert len(options) >= 2
        assert len({o.id for o in options}) == len(options)
        assert all(o.input_usd_per_million > 0 and o.output_usd_per_million > 0 for o in options)

    def test_report_prints_and_writes_the_job_summary(self, tmp_path: Path, monkeypatch, capsys) -> None:
        from cost_tracker import report_cost

        summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        tracker = CostTracker(tmp_path / "c.json", budget_usd=0.90)
        tracker.record_call(input_tokens=1000, output_tokens=200)
        report_cost(tracker)
        assert "of $0.90 budget, 1 calls" in summary.read_text(encoding="utf-8")
        assert "AI cost this month" in capsys.readouterr().out
        report_cost(None)  # nothing to report, no error
