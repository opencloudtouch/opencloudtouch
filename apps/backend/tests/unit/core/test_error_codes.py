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


_DLNA_CODES = {
    "dlna_server_not_found",
    "dlna_server_timeout",
    "dlna_object_not_found",
    "dlna_upstream_error",
    "dlna_native_slots_affected",
    "dlna_native_unavailable",
    "dlna_folder_no_audio_first",
    "dlna_preset_not_streamable",
    "dlna_migration_failed",
    "dlna_speaker_no_account",
}


def test_dlna_codes_are_registered():
    snapshot = set(_SNAPSHOT.read_text(encoding="utf-8").split())
    assert _DLNA_CODES <= set(_all_codes())
    assert _DLNA_CODES <= snapshot
