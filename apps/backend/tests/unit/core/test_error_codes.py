"""Registry test for core/error_codes.py (public error-code contract)."""

import re
from pathlib import Path

from opencloudtouch.core import error_codes

_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_SNAPSHOT = Path(__file__).parent / "error_codes_snapshot.txt"


def _all_codes() -> list[str]:
    return [
        value
        for name, value in vars(error_codes).items()
        if name.isupper() and isinstance(value, str)
    ]


def test_all_codes_match_pattern():
    for code in _all_codes():
        assert _PATTERN.match(code), code


def test_codes_are_unique():
    codes = _all_codes()
    assert len(codes) == len(set(codes))


def test_registry_is_superset_of_committed_snapshot():
    """Codes are public contract: removing or renaming one fails this test."""
    snapshot = {
        line.strip() for line in _SNAPSHOT.read_text().splitlines() if line.strip()
    }
    missing = snapshot - set(_all_codes())
    assert not missing, f"error codes removed or renamed: {sorted(missing)}"
