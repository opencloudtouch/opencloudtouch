#!/usr/bin/env bash
# Guard hook: abort pre-commit if formatters modified any staged files.
# Place AFTER all formatting hooks, BEFORE test/lint hooks.
# If git diff detects unstaged changes in staged files, a formatter changed them
# → remaining hooks (tests, lint) would run on stale content → waste of time.

changed=$(git diff --name-only)
if [ -n "$changed" ]; then
  echo ""
  echo "⚠️  Formatter modified files — aborting remaining hooks."
  echo "   Re-stage and commit again: git add -u && git commit"
  echo ""
  echo "   Modified files:"
  echo "$changed" | sed 's/^/     /'
  echo ""
  exit 1
fi
