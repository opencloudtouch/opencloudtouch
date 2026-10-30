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
