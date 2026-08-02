# Git Hooks

OpenCloudTouch uses [pre-commit](https://pre-commit.com) to run checks automatically before you commit and push. Configuration lives in [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) at the repo root.

## Setup

```bash
chmod +x scripts/install-hooks.sh
./scripts/install-hooks.sh
```

This installs pre-commit and registers the hooks for both the `pre-commit` and `pre-push` git stages.

## What runs on `git commit`

| Hook | Purpose |
|------|---------|
| `check-git-user` | Blocks the commit if `git config user.name`/`user.email` looks like a corporate identity (e.g. an internal employee ID pattern or a blocked corporate email domain) — prevents accidentally committing with the wrong identity. |
| `ruff` | Lints backend Python code (`apps/backend/`) — read-only, no auto-fix. |
| `check-yaml`, `check-json` | Validates YAML/JSON syntax (JSON check excludes `tsconfig*.json`, which allows comments). |
| `check-merge-conflict`, `check-case-conflict` | Blocks unresolved merge-conflict markers and filename case collisions. |
| `detect-private-key` | Blocks commits containing what looks like a private key. |
| `bandit` | Security-scans backend source (`apps/backend/src/`, tests excluded). |
| `commitizen` (commit-msg stage) | Validates the commit message follows [Conventional Commits](CONVENTIONAL_COMMITS.md). |
| `pytest-unit` | Runs backend unit tests — only when backend files, `pyproject.toml`, or `requirements*.txt` changed. |
| `vitest` | Runs frontend unit tests — only when frontend files, `package.json`, or `apps/backend/openapi.yaml` changed. |
| `eslint` | Lints frontend code. |
| `no-js-tests` | Blocks new `.js` test files (the project standardized on `.ts`/`.tsx`). |

Formatters (black, prettier, `ruff --fix`, trailing-whitespace/end-of-file fixers) are **not** run as local pre-commit hooks — they run in a CI autoformat job that commits fixes back to the branch (see `.github/workflows/ci.yml`).

`fail_fast: true` is set — the hook chain stops at the first failure instead of running everything and reporting all failures at once.

## What runs on `git push`

| Hook | Purpose |
|------|---------|
| `check-mojibake` | Scans the repo for CP1252-as-UTF-8 encoding corruption (mojibake). |
| `unit-tests-must-pass` | Runs the full backend + frontend unit test suite (`npm run test:unit`) — mandatory, must be 100% green. |
| `mypy-check` | Type-checks the backend (`apps/backend/src/opencloudtouch/`). |

## Bypassing hooks

Don't use `git commit --no-verify` / `git push --no-verify` to skip a failing hook — fix the underlying issue instead. The hooks exist because CI would reject the same problems anyway; skipping locally just delays the feedback.
