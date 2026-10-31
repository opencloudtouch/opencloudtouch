"""The handbook docs/WORKFLOW.md cannot drift from the implementation.

Every snippet between ``<!-- snippet:<name> -->`` and ``<!-- /snippet -->`` is rendered from the frozen
fixtures by ``oct_status.tools.render_doc_snippets``; after an intended renderer change regenerate with::

    cd scripts && python -m oct_status.tools.render_doc_snippets --write
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from oct_status.commands import COMMANDS
from oct_status.model import Phase
from oct_status.tools import render_doc_snippets as tool
from oct_status.violations import RULES

DOC = Path(__file__).resolve().parents[3] / "docs" / "WORKFLOW.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _slug(heading: str) -> str:
    """GitHub's heading anchor: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def _headings(text: str) -> list[str]:
    out, fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        if not fence and (m := re.match(r"^#{1,6}\s+(.+?)\s*$", line)):
            out.append(m[1])
    return out


def _section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, f"section '## {title}' missing"
    return match[1]


async def test_docs_snippets_match_renderer():
    rendered = await tool.render_all()
    in_doc = tool.extract(_doc())
    assert set(in_doc) == set(rendered), "snippet names in the doc and in the renderer differ"
    for name, text in rendered.items():
        assert in_doc[name] == text, f"snippet {name} is stale; regenerate with render_doc_snippets --write"


def test_every_rule_has_an_anchor():
    slugs = [_slug(h) for h in _headings(_doc())]
    rule_slugs = {s for s in slugs if re.match(r"v0\d-", s)}
    assert rule_slugs == {rule.anchor for rule in RULES.values()}
    assert len(rule_slugs) == len([s for s in slugs if re.match(r"v0\d-", s)]), "an anchor exists twice"
    for rule_id, rule in RULES.items():
        heading = next(h for h in _headings(_doc()) if _slug(h) == rule.anchor)
        start = re.search(rf"^#{{1,6}}\s+{re.escape(heading)}\s*$", _doc(), re.MULTILINE)
        assert start
        following = _doc()[start.end() :]
        nxt = re.search(r"^#{1,3} ", following, re.MULTILINE)
        body = following[: nxt.start()] if nxt else following
        assert "Wrong" in body and "Right" in body, f"{rule_id} needs a wrong and a right example"
        assert "What happened" in body and "Expected" in body and "Next steps" in body, rule_id


def test_every_phase_has_an_anchor():
    """The guide's "You are here" line links to WORKFLOW.md#<phase>."""
    slugs = [_slug(h) for h in _headings(_doc())]
    for phase in Phase:
        assert slugs.count(phase.value) == 1, f"anchor #{phase.value} missing or duplicated"


def test_labels_documented_with_their_colors():
    rows = [line for line in _doc().splitlines() if line.startswith("| `")]
    for entry in yaml.safe_load((Path(tool.PACKAGE) / "labels.yml").read_text(encoding="utf-8"))["labels"]:
        found = [r for r in rows if r.startswith(f"| `{entry['name']}` |")]
        assert found, f"label {entry['name']} is not in a reference table"
        assert any(f"| #{entry['color']} |" in r for r in found), f"label {entry['name']}: wrong or no color"


def test_commands_documented():
    reference = _section(_doc(), "Command reference")
    for name in sorted(COMMANDS):
        assert f"`/oct {name}" in reference, f"/oct {name} is not in the command reference"


def test_extract_and_replace_round_trip():
    doc = "a\n<!-- snippet:x -->\nold\n<!-- /snippet -->\nb\n<!-- snippet:y -->\n<!-- /snippet -->\n"
    assert tool.extract(doc) == {"x": "old", "y": ""}
    new = tool.replace(doc, {"x": "new\ntext", "y": "z"})
    assert tool.extract(new) == {"x": "new\ntext", "y": "z"}
    assert new.startswith("a\n") and "\nb\n" in new


def test_replace_rejects_unknown_snippet():
    with pytest.raises(KeyError):
        tool.replace("<!-- snippet:nope -->\n<!-- /snippet -->\n", {})


def test_fence_is_longer_than_any_backtick_run():
    assert tool.fence("a ```b``` c").startswith("````markdown\n")
    assert tool.fence("plain").startswith("```markdown\n")


def test_cli_prints_every_snippet(capsys):
    assert tool.main([]) == 0
    out = capsys.readouterr().out
    for name in tool.extract(_doc()):
        assert f"<!-- snippet:{name} -->" in out


def test_cli_write_updates_a_copy(tmp_path):
    copy = tmp_path / "WORKFLOW.md"
    copy.write_text(re.sub(r"(<!-- snippet:[^>]+ -->\n).*?(<!-- /snippet -->)", r"\1\2", _doc(), flags=re.DOTALL))
    assert tool.main(["--write", str(copy)]) == 0
    assert copy.read_text(encoding="utf-8") == _doc()
