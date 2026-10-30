# Auto-apply criteria

Apply review findings automatically only when they are one of:

- unused imports
- formatting
- typos
- documentation (comments, docstrings, Markdown files)

Do not auto-apply any other finding. Leave it as a review comment for a human.

Never auto-apply changes to:

- authentication code
- SSH code
- setup wizard code
- device protocol code
- `.github/`
- `.claude/`
- `.gitar/`
- `scripts/oct_status/`
- `.gitignore`
- `CLAUDE.md`
