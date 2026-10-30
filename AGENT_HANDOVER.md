# AGENT_HANDOVER

Machine-readable handover from a prior agent session. Written for an AI coding agent to act on directly — not for a human to read. Do not preserve this file's prose style in commits/PRs; it exists only to transfer state.

**Freshness warning:** every fact below was verified at the timestamp/commit noted. Git state may have moved since (pushes, merges, rebases). Before acting on any claim, re-verify it live (`git log`, `git status`, `gh pr view`) rather than trusting this file blindly. If a fact here contradicts live state, live state wins — treat this file as a lead, not ground truth.

Verified at: 2026-08-30, repo `opencloudtouch/opencloudtouch`, main repo worktree `E:/DEV/Projekte/opencloudtouch`.

Language convention for this repo (already in global `~/.claude/CLAUDE.md`, restated here for completeness): all repo content (code, comments, commit messages, PR titles/descriptions, docs) in English. Chat replies to the user in German.

---

## Task list, in suggested order

### 1. Reconcile the dirty working tree in THIS worktree (main repo)

Current branch here is `feat/replace-bose-ntp-servers`, at commit `f96b5b1`. **This is not the user's own branch** — it is a local checkout of an external contributor's fork PR:

```
gh pr view 429 --json headRefOid,headRepository,headRepositoryOwner
→ headRefOid: f96b5b104cb90db3b12d44e975ced04c3ad67c0a (matches HEAD here)
→ headRepository: geertmeersman/opencloudtouch, owner: Geert Meersman
```

**Do not push this branch to `origin`.** It was checked out locally (likely via `gh pr checkout 429`) purely for review/testing of PR #429. Verify PR #429's current state before touching this checkout further (it may have been merged/closed/updated since).

On top of that checkout, `git status --porcelain=v1` shows:

```
 M deployment/local/deploy-to-server.ps1
?? .claude/
?? .mcp.json
?? .serena/
?? .worktrees/
```

These are unrelated to PR #429 — the user's own local, uncommitted work:

- **`deployment/local/deploy-to-server.ps1`**: Docker/SSH deploy-script fix (better error messages when Docker access fails, `-UseSudo` handling, `ssh -tt` when sudo is used). The user may still be actively editing this — **ask before committing**. If confirmed done, extract onto its own branch off `main` (not off the PR #429 checkout), e.g. `fix/deploy-script-sudo-docker`, commit, push. Suggested method to avoid disturbing this checkout: `git worktree add -b fix/deploy-script-sudo-docker .worktrees/tmp-deploy-fix origin/main`, copy the file content over, commit, push, then `git worktree remove` the temp worktree.
- **`.claude/`, `.mcp.json`, `.serena/`, `.worktrees/`**: local tool/editor state, not project source. Do not commit these. They will start being auto-ignored once the PR from task 2 below is merged to `main`. Until then, just leave them untracked — do not `rm` them, they may contain live tool state (MCP config, Serena project index, other active worktrees).

### 2. Open PRs for two already-pushed branches

Both are fully committed and pushed to `origin`, but have **no PR yet**:

- `feature/shorten_supporters_long_names` (commit `82b7dd9`) — fixes `apps/frontend/src/pages/aboutUtils.ts::cleanName()` to strip everything from `@` onward in supporter names unless `@` is the very first character. Has passing tests in `apps/frontend/src/pages/aboutUtils.test.ts`. Ready for PR against `main` as-is.
- `chore/gitignore-tool-dirs` (commit `18a49ef`) — adds `.worktrees/`, `.claude/`, `.mcp.json`, `.serena/` to `.gitignore`. Ready for PR against `main` as-is. Confirmed no conflict with the already-merged PR #409 (`fix/pyc-negative-dentry-growth`) — that PR's final merged diff did not touch these ignore entries (verified via `git show origin/main:.gitignore`, no `.worktrees/` entry present).

Use `gh pr create --base main --head <branch> --title "..." --fill` or equivalent, after confirming title/body with the user if your instructions require that.

### 3. Telnet wizard WIP — uncommitted-turned-committed, unpushed

Branch `feat/352-wave-telnet-support` already has an **open PR #355**. A prior session found 5 orphaned, uncommitted files in this same main-repo checkout (unrelated to PR #429 above, predating it) that belonged to this feature, and committed them onto `feat/352-wave-telnet-support` **without pushing** (commit `c8b7cf4`, message `wip(telnet): add wizard steps for Telnet config/reboot + security tests`):

- `apps/frontend/src/components/wizard/StepTelnetConfig.tsx`
- `apps/frontend/src/components/wizard/StepTelnetReboot.tsx`
- `apps/frontend/tests/unit/TelnetWizardFlow.test.tsx`
- `apps/backend/tests/unit/setup/test_security_validation.py`
- `apps/backend/tests/unit/setup/test_wizard_device_lock.py`

These were only syntax-checked (`python -m py_compile`), never actually run — the backend venv in this environment had a broken interpreter path (`.venv/Scripts/python.exe` pointed at a non-existent `C:\Python313\python.exe`). Before pushing:

1. Fix or recreate the backend venv (`apps/backend/.venv` or repo-root `.venv`), then run the two new backend test files plus the existing telnet suite (`apps/backend/tests/unit/setup/test_telnet_config_service.py`) to make sure nothing regressed.
2. Run the new frontend test (`apps/frontend/tests/unit/TelnetWizardFlow.test.tsx`) with `npx vitest run`.
3. Confirm with the user that this WIP is actually meant to ship on PR #355 — it was relocated here based on import-path matching (`opencloudtouch.setup.wizard_service`, `opencloudtouch.setup.api_models`, i.e. this branch's flat module layout, not `refactor/setup-wizard-module`'s new `setup/wizard/` subpackage) and content correlation, not explicit user confirmation of intent for these specific 5 files.
4. Only then `git push` on `feat/352-wave-telnet-support` to update PR #355.

### 4. Remove the last leftover worktree

`.worktrees/frontend-unit-test-coverage` still exists, holding branch `feature/shorten_supporters_long_names` (fully pushed, commit `82b7dd9` — safe either way). A prior agent session's shell was running from inside it and deliberately left it for a follow-up session to avoid deleting its own cwd mid-task.

```
git -C "E:/DEV/Projekte/opencloudtouch" worktree remove ".worktrees/frontend-unit-test-coverage"
```

Known failure mode encountered twice already this week with other worktrees in this repo: the OS refuses to delete the physical folder (`Permission denied` / `Device or resource busy`), almost always because VSCode still holds a file handle open on it (open tab, multi-root workspace folder, or its file watcher). What actually happens: **git still successfully deregisters the worktree** (deletes `.git/worktrees/<name>/` and the working tree's `.git` link) even when the OS delete fails — the folder becomes a plain, git-disconnected leftover directory, not a broken worktree. If this happens:

1. Confirm it's deregistered: `git worktree list` should no longer show it.
2. Ask the user to fully close VSCode (not just the tab).
3. Retry plain deletion: `rm -rf ".worktrees/frontend-unit-test-coverage"` (or `Remove-Item -Recurse -Force` in PowerShell).

No data is at risk in either outcome since the branch is already fully pushed.

### 5. Repo-wide git commit-graph corruption (low priority, cosmetic so far)

Nearly every git command in this repo prints:

```
warning: unable to find all commit-graph files
```

and some print:

```
error: failed to rename temporary commit-graph file
error: failed to write commit-graph
error: task 'commit-graph' failed
```

Has not blocked any operation observed so far, but is repo-wide (reproduces in every worktree) and pre-existing (noted in a session before this one too). Suggested fix, lowest-risk first:

1. `git commit-graph write --reachable --changed-paths` in the main repo.
2. If that itself fails: delete `.git/objects/info/commit-graph*` files, then retry step 1, or run `git maintenance run --task=commit-graph`.
3. Verify by running any `git log`/`git status` afterward and confirming the warning is gone.

---

## Context the user gave this repo's agents, for reference

- Global instruction (`~/.claude/CLAUDE.md`): chat replies to this user always in German; all repo content always in English.
- The user manages many parallel `git worktree`s in this repo and finds VSCode's handling of them unreliable (file locks preventing cleanup, as seen in task 4). Expect this to keep happening; the workaround in task 4 is now known-good.
- `gh` CLI is authenticated in this environment (account `scheilch`, full `repo`/`workflow` scopes) — prefer it over guessing PR numbers from memory/notes, which have been found stale (e.g. an earlier note claimed the `frontend/unit-test-coverage` branch was PR #433; it is actually **PR #431**).
