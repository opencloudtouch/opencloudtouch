# Conventional Commits

OpenCloudTouch enforces [Conventional Commits](https://www.conventionalcommits.org/) on every commit message via the `commitizen` git hook (commit-msg stage, see [GIT_HOOKS.md](GIT_HOOKS.md)). This isn't just a style preference — `commitizen` uses the commit history to compute version bumps and generate `CHANGELOG.md` (`tool.commitizen` in [`apps/backend/pyproject.toml`](../apps/backend/pyproject.toml)).

## Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

- `type` — required, see table below.
- `scope` — optional, lowercase, names the affected area (see examples from this repo's own history below).
- `subject` — imperative mood ("add", not "added"/"adds"), no trailing period.
- `body`/`footer` — optional, free text. Use the footer for `BREAKING CHANGE: ...` or issue references (`Closes #123`).

## Types

| Type | Use for | Affects version bump? |
|------|---------|------------------------|
| `feat` | A new feature | Minor |
| `fix` | A bug fix | Patch |
| `docs` | Documentation only | — |
| `test` | Adding or correcting tests | — |
| `refactor` | Code change that neither fixes a bug nor adds a feature | — |
| `perf` | Performance improvement | Patch |
| `ci` | CI/CD configuration or workflow changes | — |
| `chore` | Maintenance (deps, tooling, version bumps) that doesn't fit elsewhere | — |

A `!` after the type/scope (e.g. `feat!:`) or a `BREAKING CHANGE:` footer triggers a major version bump.

## Real examples from this repo's history

```
fix(docker): stop shipping/regenerating deleted bytecode, use curl health check
fix(ci): skip auto-format for dependabot PRs (#397)
chore(deps-dev): bump systeminformation from 5.31.6 to 5.31.17 (#400)
chore: bump version to 1.5.5
ci: add mark_as_latest input for Docker image tagging in workflows
fix: resolve memory leak — add cache eviction, cleanup handlers, memory monitoring (#366) (#372)
```

Common scopes seen in this repo: `docker`, `ci`, `deps`, `deps-dev`, `devices`, `version`. Scopes are free-form — pick whatever names the affected module/area clearly; don't invent a scope just to have one.

## Version bumps & releases

`commitizen` reads the accumulated commit types since the last tag to decide the next version (`tag_format = "v$version"` in `pyproject.toml`) and updates `CHANGELOG.md` automatically (`update_changelog_on_bump = true`). This is why the type matters beyond documentation — an incorrectly typed commit can cause a wrong version bump or an empty changelog entry.

## Also see

- [Git Hooks](GIT_HOOKS.md) — how the commit-msg validation is enforced locally
- [CONTRIBUTING.md](../.github/CONTRIBUTING.md) — full contribution guide
