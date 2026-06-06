#!/usr/bin/env python3
"""
Mojibake detector — checks source files for CP1252-as-UTF8 encoding corruption.

Exit 0: clean. Exit 1: mojibake found (prints offending lines).

Excluded paths/patterns:
  - node_modules/, .git/, __pycache__/, dist/, .venv/, .local/
  - .github/workflows/   (CI YAML may contain mojibake pattern strings as docs)
  - tests/e2e/           (Cypress tests deliberately assert on mojibake absence)
  - scripts/check-mojibake.py  (this file itself contains the patterns as strings)

Detection: sequences that are valid UTF-8 but look like Latin-1/CP1252
double-encoded. We look for the most common: Ã + follow-byte (covers é, ü, ö …)
and â€ + follow-byte (smart quotes, dashes) and âš/â›/â† emoji corruption.
"""
import sys
import io

# Force UTF-8 output to avoid UnicodeEncodeError on CP1252 terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import re
import sys
import pathlib

# ---------------------------------------------------------------------------
# Patterns that indicate mojibake (not intentional unicode)
# ---------------------------------------------------------------------------
# Ã followed by a byte in range 0x80-0xBF  → typical CP1252 vowel-with-accent
# â€ followed by follow-byte               → smart quotes, en/em-dash
# âš or â› followed by follow-byte         → emoji corruption (⚙️ ⚠️ etc.)
# â\x9d                                    → ❌ ❓ etc. corruption
MOJIBAKE_PATTERN = re.compile(
    r"Ã[\x80-\xBF]"                  # Ã + continuation → é ü ö etc.
    r"|â€[\x80\x93\x94\x98\x99\x9c\x9d]"  # smart quotes / dashes
    r"|â[šûü]"                        # ⚙ ⚠ etc.
    r"|â\x9d"                         # ❌ ❓ etc.
    r"|Ã\x83"                         # double-encoded Ã
)

# ---------------------------------------------------------------------------
# File extensions to check
# ---------------------------------------------------------------------------
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml",
              ".md", ".css", ".html"}

# ---------------------------------------------------------------------------
# Path segments that are entirely excluded
# ---------------------------------------------------------------------------
EXCLUDED_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", ".venv", ".local",
}

# ---------------------------------------------------------------------------
# File-level exclusions (relative globs matched against full path string)
# ---------------------------------------------------------------------------
EXCLUDED_PATH_FRAGMENTS = [
    "/.github/",                          # CI YAML contains pattern as docs
    "/tests/e2e/",                        # Cypress: intentional mojibake assertions
    "\\tests\\e2e\\",                     # Windows path variant
    "\\.github\\",                        # Windows variant
    "scripts/check-mojibake.py",          # This file
    "scripts\\check-mojibake.py",         # Windows variant
    "scripts/fix-mojibake.py",            # Fix script contains mojibake chars as data
    "scripts\\fix-mojibake.py",           # Windows variant
    "icy_samples.json",                   # Raw ICY metadata samples (binary data)
]

# ---------------------------------------------------------------------------
# Per-line skip marker: lines ending with this comment are excluded
# ---------------------------------------------------------------------------
SKIP_MARKER = "check-mojibake: skip"


def should_skip(path: pathlib.Path) -> bool:
    parts = path.parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    path_str = str(path)
    return any(frag in path_str for frag in EXCLUDED_PATH_FRAGMENTS)


def check_file(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line) with mojibake."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    return [
        (i + 1, line)
        for i, line in enumerate(text.splitlines())
        if MOJIBAKE_PATTERN.search(line) and SKIP_MARKER not in line
    ]


def main() -> int:
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
    total_issues = 0
    files_checked = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in EXTENSIONS:
            continue
        if should_skip(path):
            continue

        files_checked += 1
        hits = check_file(path)
        if hits:
            rel = path.relative_to(root)
            print(f"\n❌ {rel}")
            for lineno, line in hits:
                preview = line.strip()[:120]
                print(f"   L{lineno}: {preview}")
            total_issues += len(hits)

    print(f"\n{'─' * 60}")
    print(f"Checked {files_checked} files.")
    if total_issues:
        print(f"❌ Found {total_issues} mojibake occurrence(s). Fix before merge.")
        return 1
    else:
        print("✅ No mojibake detected.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
