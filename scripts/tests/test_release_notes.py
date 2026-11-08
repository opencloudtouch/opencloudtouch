import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_notes import commit_notes, extract, promote  # noqa: E402

CL = "# Changelog\n\n---\n\n## [Unreleased]\n\n### Added\n- New thing\n\n---\n\n## [1.0.0] - 2026-01-01\n\n- old\n"


def test_promote_keeps_curated_text():
    out = promote(CL, "2.0.0", "2026-11-08")
    assert "## [2.0.0] - 2026-11-08" in out
    assert extract(out, "2.0.0") == "### Added\n- New thing"
    assert "_No changes yet._" in out.split("## [2.0.0]")[0]
    assert extract(out, "1.0.0") == "- old"


def test_promote_is_idempotent_and_falls_back_to_commits():
    once = promote(CL, "2.0.0", "2026-11-08")
    assert promote(once, "2.0.0", "2026-11-09") == once
    empty = CL.replace("### Added\n- New thing", "_No changes yet._")
    out = promote(empty, "2.0.1", "2026-11-09", ["fix(ui): a bug", "chore: x", "feat: y"])
    assert extract(out, "2.0.1") == "### Added\n- y\n\n### Fixed\n- a bug"


def test_commit_notes_empty():
    assert commit_notes(["chore: x"]) == ""


def test_bare_bullet_list_keeps_its_first_marker():
    cl = "# C\n\n## [Unreleased]\n\n- first item\n- last item-\n\n---\n\n## [1.0.0] - 2026-01-01\n\n- old\n"
    out = promote(cl, "2.0.0", "2026-11-08")
    assert extract(out, "2.0.0") == "- first item\n- last item-"
