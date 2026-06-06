#!/usr/bin/env python3
"""
Fix CP1252-as-UTF8 mojibake in locale and source files.

Algorithm: scan each character; for consecutive non-ASCII sequences, attempt to
reverse the double-encoding: encode as CP1252 bytes → decode as UTF-8. If that
succeeds, use the decoded result. If it fails, leave the segment unchanged.

This safely handles MIXED files (some text correct, some corrupted) because:
- Correctly-encoded non-ASCII chars (e.g. é = U+00E9) produce a single byte
  0xE9, which is not valid standalone UTF-8, so decode fails → left unchanged.
- Mojibake sequences (e.g. Ã© = U+00C3 U+00A9) produce bytes C3 A9, which
  ARE valid UTF-8 (é) → fixed.
"""

import pathlib
import sys

# ---------------------------------------------------------------------------
# CP1252-undefined bytes (0x81, 0x8D, 0x8F, 0x90, 0x9D) have no official
# Unicode mapping. Python stores them as U+0081 etc. (C1 control characters).
# We map them back to their original byte values.
# ---------------------------------------------------------------------------
CTRL_MAP: dict[str, int] = {
    '\x81': 0x81,
    '\x8d': 0x8d,
    '\x8f': 0x8f,
    '\x90': 0x90,
    '\x9d': 0x9d,
}


def char_to_cp1252_byte(c: str) -> int | None:
    """Return the CP1252 byte for a single character, or None on failure."""
    if c in CTRL_MAP:
        return CTRL_MAP[c]
    try:
        b = c.encode('cp1252')
        return b[0] if len(b) == 1 else None
    except (UnicodeEncodeError, LookupError):
        return None


def try_fix_segment(segment: str) -> str:
    """Try to reverse-decode a non-ASCII segment via CP1252 → UTF-8."""
    raw = bytearray()
    for c in segment:
        byte = char_to_cp1252_byte(c)
        if byte is None:
            # Not encodable as CP1252 → cannot fix this segment
            return segment
        raw.append(byte)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return segment


def fix_content(text: str) -> str:
    """Fix CP1252-as-UTF8 mojibake in a string, preserving ASCII content."""
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if ord(c) < 0x80:
            result.append(c)
            i += 1
        else:
            # Collect consecutive non-ASCII characters
            j = i
            while j < n and ord(text[j]) >= 0x80:
                j += 1
            segment = text[i:j]
            result.append(try_fix_segment(segment))
            i = j
    return ''.join(result)


# ---------------------------------------------------------------------------
# Files to fix
# ---------------------------------------------------------------------------
FILES_TO_FIX = [
    'apps/frontend/src/i18n/locales/fr.json',
    'apps/frontend/src/i18n/locales/sv.json',
    'apps/frontend/src/i18n/locales/pl.json',
    'apps/frontend/src/i18n/locales/ja.json',
]


def fix_file(path: pathlib.Path) -> bool:
    """Fix a file in-place. Returns True if the file was modified."""
    raw = path.read_bytes()

    # Detect and strip UTF-8 BOM
    bom = b'\xef\xbb\xbf'
    has_bom = raw.startswith(bom)
    content_bytes = raw[len(bom):] if has_bom else raw

    text = content_bytes.decode('utf-8')
    fixed = fix_content(text)

    if fixed == text:
        return False

    # Write back with original BOM status
    output = (bom if has_bom else b'') + fixed.encode('utf-8')
    path.write_bytes(output)
    return True


def main() -> int:
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('.')
    any_fixed = False
    for rel in FILES_TO_FIX:
        path = root / rel
        if not path.exists():
            print(f'  SKIP (not found): {rel}')
            continue
        modified = fix_file(path)
        status = '✅ fixed' if modified else '— unchanged'
        print(f'  {status}: {rel}')
        if modified:
            any_fixed = True

    if any_fixed:
        print('\nAll files processed. Run check-mojibake.py to verify.')
    else:
        print('\nNo changes needed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
