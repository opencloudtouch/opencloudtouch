"""Repository instruction files for Gitar and Claude agents (spec sections 7 and 8)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_gitar_rules_explain_status_system():
    text = _read(".gitar/rules/oct-status.md")
    for needle in (
        "<!-- oct-status:v1 -->",
        "<!-- /oct-status -->",
        "<!-- oct-next:v1 -->",
        "phase:",
        "wait:",
        "resolution:",
        "Conventional Commits",
        "/oct accept-paths",
        "@gitar-bot",
    ):
        assert needle in text, needle
    for path in (".github/", ".claude/", ".gitar/", "scripts/oct_status/"):
        assert path in text, path


def test_gitar_apply_criteria_skip_sensitive_areas():
    text = _read(".gitar/config/apply.md").lower()
    for needle in (
        "unused import",
        "formatting",
        "typo",
        "documentation",
        "authentication",
        "ssh",
        "setup wizard",
        "device protocol",
        ".github/",
        ".claude/",
        ".gitar/",
        "scripts/oct_status/",
    ):
        assert needle in text, needle


def _protected_prefixes() -> list[str]:
    from oct_status.config import load_config

    patterns = load_config(ROOT / "scripts/oct_status/config.yml").protected_paths
    return [p.removesuffix("**") for p in patterns]


def test_protected_paths_cover_the_files_the_status_system_depends_on():
    from oct_status.config import load_config
    from oct_status.rules import touches_protected

    patterns = load_config(ROOT / "scripts/oct_status/config.yml").protected_paths
    for path in (
        ".github/workflows/oct-status.yml",
        ".github/pull_request_template.md",  # the guard and the DoD checklist depend on it
        ".github/ISSUE_TEMPLATE/task_specification.yml",  # the Definition of Ready checklist
        ".github/dependabot.yml",
        ".claude/settings.json",  # registers the hooks
        ".gitar/rules/oct-status.md",
        "scripts/oct_status/config.yml",
        ".gitignore",
        "CLAUDE.md",
    ):
        assert touches_protected([path], patterns) == [path], path


def test_gitar_texts_name_every_protected_path():
    """The Gitar rules and apply criteria list exactly what config.yml protects (one consistent list)."""
    rules, apply = _read(".gitar/rules/oct-status.md"), _read(".gitar/config/apply.md")
    for prefix in _protected_prefixes():
        assert f"`{prefix}`" in rules, prefix
        assert f"`{prefix}`" in apply, prefix


def test_claude_md_status_section():
    text = _read("CLAUDE.md")
    assert "## Status system" in text
    assert "docs/WORKFLOW.md" in text
    section = text.split("## Status system", 1)[1].split("\n## ", 1)[0]
    assert len([ln for ln in section.strip().splitlines() if ln.strip()]) <= 10
    for needle in ("/oct", "oct-status", "phase", "wait", "resolution", "guide comment", "subagent"):
        assert needle in section, needle
    assert "Never bypass hooks" in text


def test_every_gitar_rule_has_the_frontmatter_gitar_expects():
    """Gitar reads `.gitar/rules/*.md` as rules: YAML frontmatter with title, type, when and actions."""
    rules = sorted((ROOT / ".gitar" / "rules").glob("*.md"))
    assert rules
    for path in rules:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), path.name
        header = text.split("\n---\n", 1)[0]
        for key in ("title:", "type:", "when:", "actions:"):
            assert key in header, f"{path.name} lacks {key}"
