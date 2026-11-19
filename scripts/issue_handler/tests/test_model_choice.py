"""Model choice: the first configured candidate that the API key can use."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from model_choice import DEFAULT_CANDIDATES, candidates, pick_model

SETTINGS = {
    "openai_models": [
        {"id": "cheap", "input_usd_per_million": 0.05, "output_usd_per_million": 0.25},
        {"id": "mid", "input_usd_per_million": 0.10, "output_usd_per_million": 0.60},
    ]
}


def _client(*ids: str) -> AsyncMock:
    c = AsyncMock()
    c.models.list.return_value = SimpleNamespace(data=[SimpleNamespace(id=i) for i in ids])
    return c


@pytest.mark.asyncio
async def test_takes_the_first_available_candidate_with_its_prices() -> None:
    choice = await pick_model(_client("mid", "other"), SETTINGS)
    assert (choice.id, choice.input_usd_per_million, choice.output_usd_per_million) == ("mid", 0.10, 0.60)


@pytest.mark.asyncio
async def test_prefers_the_cheaper_one_when_both_exist() -> None:
    assert (await pick_model(_client("mid", "cheap"), SETTINGS)).id == "cheap"


@pytest.mark.asyncio
async def test_falls_back_to_the_first_candidate_when_none_is_available_or_listing_fails() -> None:
    assert (await pick_model(_client("unrelated"), SETTINGS)).id == "cheap"
    broken = AsyncMock()
    broken.models.list.side_effect = RuntimeError("401")
    assert (await pick_model(broken, SETTINGS)).id == "cheap"
    assert (await pick_model(None, SETTINGS)).id == "cheap"


def test_defaults_when_rules_yml_has_no_list() -> None:
    assert candidates({}) == DEFAULT_CANDIDATES


@pytest.mark.asyncio
async def test_models_missing_from_the_api_are_logged_and_put_into_the_job_summary(
    tmp_path, monkeypatch, capsys, caplog
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with caplog.at_level("WARNING"):
        choice = await pick_model(_client("mid"), SETTINGS)
    assert choice.id == "mid"
    assert "cheap" in caplog.text and "not available" in caplog.text
    assert '"stage": "models"' in capsys.readouterr().out
    assert "cheap" in summary.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_nothing_is_announced_when_all_candidates_exist(capsys) -> None:
    await pick_model(_client("cheap", "mid"), SETTINGS)
    assert capsys.readouterr().out == ""
