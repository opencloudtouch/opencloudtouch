# OpenCloudTouch status system rules for Gitar

This repository runs an automated status system (`oct-status`). It owns the status block, a set of labels and one guide comment on every issue and pull request. Follow these rules whenever you comment, edit, summarise or push.

## Status block

- The PR/issue description may contain a block that starts with `<!-- oct-status:v1 -->` and ends with `<!-- /oct-status -->`.
- Never edit, move, reformat or delete that block, including its HTML comment markers. If you rewrite or enhance the description, keep everything between the markers byte for byte and leave the text around it intact.

## Labels

- Labels starting with `phase:`, `wait:` or `resolution:` are owned by `oct-status`. Never set or remove them. Your own `gitar-*` labels are fine.

## Guide comment

- Every artifact has exactly one guide comment that carries the marker `<!-- oct-next:v1 -->`. It lists the next steps. Never reply to it, never edit it and never quote it in a new comment.
- Your own comments must never start with `gitar` and must never mention `@gitar-bot` inside text that belongs to the status system (block, guide comment, or anything quoting them), so you do not trigger yourself.

## Commits

- Any commit you make follows Conventional Commits (`type(scope): subject`, for example `style: remove unused import`) and is written in English.
- Commit messages contain no references to AI tools or assistants and no `Co-Authored-By` or similar trailers (repository rule).

## Protected paths

- Pushes to `.github/`, `.claude/`, `.gitar/`, `scripts/oct_status/`, `.gitignore` and `CLAUDE.md` are held by `oct-status` until a maintainer acknowledges them with `/oct accept-paths`. Avoid touching these paths (moving or renaming a file out of them counts as well); if a fix needs them, describe it in a review comment instead of pushing.
