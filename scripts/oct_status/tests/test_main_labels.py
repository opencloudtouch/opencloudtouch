"""Tests for the CLI entry point (labels mode)."""

from __future__ import annotations

import runpy
import sys

import httpx
import pytest

from oct_status import main
from oct_status.api import GitHubApi
from tests.test_labels_sync import REPO, FakeGitHub


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()

    async def no_sleep(_: float) -> None:
        return None

    def factory(token: str, repo: str) -> GitHubApi:
        return GitHubApi(token, repo, transport=httpx.MockTransport(fake.handler), sleep=no_sleep)

    monkeypatch.setattr(main, "GitHubApi", factory)
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token-value")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.delenv("BOT_PAT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return fake


def test_cli_labels_dry_run_exits_zero_and_prints_operations(fake, capsys):
    assert main.cli(["--labels", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.strip()
    assert "secret-token-value" not in out
    assert fake.writes == []


def test_cli_labels_real_run_writes(fake, capsys):
    assert main.cli(["--labels"]) == 0
    assert fake.writes
    assert fake.issues


def test_missing_repository_exits_two(fake, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_REPOSITORY")
    assert main.cli(["--labels", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert "GITHUB_REPOSITORY" in err


def test_missing_token_exits_two_without_echo(fake, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN")
    assert main.cli(["--labels", "--dry-run"]) == 2
    assert "BOT_PAT" in capsys.readouterr().err


def test_bot_pat_preferred(fake, monkeypatch):
    seen: list[str] = []
    orig = main.GitHubApi

    def spy(token: str, repo: str) -> GitHubApi:
        seen.append(token)
        return orig(token, repo)

    monkeypatch.setattr(main, "GitHubApi", spy)
    monkeypatch.setenv("BOT_PAT", "pat")
    assert main.cli(["--labels", "--dry-run"]) == 0
    assert seen == ["pat"]


def test_no_mode_exits_two(fake, capsys):
    assert main.cli([]) == 2


def test_step_summary_written(fake, monkeypatch, tmp_path, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main.cli(["--labels", "--dry-run"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    text = summary.read_text()
    assert all(f"- {ln}" in text for ln in lines)


def test_api_error_exits_one(fake, capsys):
    fake.handler = lambda request: httpx.Response(403, json={"message": "forbidden"})  # type: ignore[method-assign]
    assert main.cli(["--labels", "--dry-run"]) == 1
    assert "secret-token-value" not in capsys.readouterr().err


def test_dunder_main_wiring(fake, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["oct_status", "--labels", "--dry-run"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("oct_status", run_name="__main__")
    assert exc.value.code in (0, 2)
