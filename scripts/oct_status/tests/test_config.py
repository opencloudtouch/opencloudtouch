from pathlib import Path

from oct_status.config import load_config

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"


def test_load_config_defaults():
    cfg = load_config(CONFIG_PATH)
    assert cfg.fan_out_cap == 25
    assert cfg.strike_window_days == 60
    assert cfg.strikes_enabled_from is None


def test_actor_profiles():
    cfg = load_config(CONFIG_PATH)
    assert cfg.automation["formatter-bot"].invalidates_approval is False
    assert cfg.automation["gitar-bot[bot]"].invalidates_approval is True
    assert cfg.automation["gitar-bot[bot]"].pushes is True
    assert cfg.automation["dependabot[bot]"].block_location == "comment"
    # MA-8: Gitar commits under the User login `gitar-bot`, reviews and comments come from `gitar-bot[bot]`.
    assert cfg.automation["gitar-bot"].pushes is True
    assert cfg.automation["gitar-bot"].invalidates_approval is True


def test_only_pushing_automation_counts_as_a_pusher():
    cfg = load_config(CONFIG_PATH)
    for login in ("gitar-bot", "gitar-bot[bot]", "formatter-bot", "dependabot[bot]", "github-actions[bot]"):
        assert cfg.pushes(login), login
    # The maintainer's own local commits carry the login oct-support (MA-8): human work, not automation.
    assert cfg.automation["oct-support"].pushes is False
    for login in ("oct-support", "sonarqubecloud[bot]", "codecov-commenter", "alice", ""):
        assert not cfg.pushes(login), login
    for login in (
        "oct-support",
        "github-actions[bot]",
        "sonarqubecloud[bot]",
        "github-code-quality[bot]",
        "codecov-commenter",
    ):
        assert login in cfg.automation


def test_gates_and_protected_paths():
    cfg = load_config(CONFIG_PATH)
    assert "CI Summary" in cfg.gate_checks
    assert "SonarCloud Code Analysis" in cfg.gate_checks
    assert "Gitar" in cfg.gate_checks
    for pattern in (".github/workflows/**", "scripts/oct_status/**", ".gitar/**", ".claude/**", ".gitignore"):
        assert pattern in cfg.protected_paths


def test_bot_logins():
    assert load_config(CONFIG_PATH).bot_logins == ("oct-support", "github-actions[bot]")


def test_ledger_issue_is_validated(tmp_path):
    import pytest

    def load(value: str):
        path = tmp_path / "c.yml"
        path.write_text(f"ledger_issue: {value}\n", encoding="utf-8")
        return load_config(path)

    assert load("42").ledger_issue == 42
    assert load("null").ledger_issue is None
    for bad in ("0", "-3", "abc", "true", "1.5", "[1]"):
        with pytest.raises(ValueError):
            load(bad)
