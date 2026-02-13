# Blocking --no-verify for AI Agents in VS Code

**Problem:** AI agents (like GitHub Copilot Agent Mode) can bypass pre-commit hooks using `git commit --no-verify`, allowing commits with failing tests.

**Goal:** Prevent `--no-verify` from being used by agents while keeping it available for emergency human overrides.

---

## ⚠️ CRITICAL: Why --no-verify is Dangerous

Pre-commit hooks enforce:
- ✅ All tests must pass (351 backend + 260 frontend + 36 E2E = 100%)
- ✅ Code formatting (Black, Prettier)
- ✅ Linting (Ruff, ESLint)
- ✅ Security checks (Bandit)
- ✅ Conventional commit format

**Using `--no-verify` bypasses ALL of this** → broken commits in history.

---

## Solution 1: Git Alias Wrapper (Recommended)

Create a Git alias that replaces `git commit` with a wrapper script that **refuses --no-verify**.

### Step 1: Create Wrapper Script

**File:** `.git/hooks/commit-wrapper.sh`

```bash
#!/bin/bash
# Git commit wrapper that blocks --no-verify

# Check if --no-verify is in arguments
for arg in "$@"; do
  if [[ "$arg" == "--no-verify" || "$arg" == "-n" ]]; then
    echo "❌ ERROR: --no-verify is STRICTLY FORBIDDEN"
    echo ""
    echo "Pre-commit hooks exist for a reason:"
    echo "  - Ensures ALL tests pass (Backend + Frontend + E2E)"
    echo "  - Validates code formatting and linting"
    echo "  - Prevents security issues"
    echo ""
    echo "If hooks fail:"
    echo "  1. Fix the actual problem (failing tests, format, etc.)"
    echo "  2. Do NOT bypass hooks"
    echo ""
    echo "For emergency human override (HUMANS ONLY):"
    echo "  Use: git-commit-force-override (see docs/GIT_HOOKS.md)"
    exit 1
  fi
done

# All good - run normal git commit
exec git commit "$@"
```

### Step 2: Make Script Executable

**PowerShell:**
```powershell
# Git Bash required for executable permission
git update-index --chmod=+x .git/hooks/commit-wrapper.sh
```

### Step 3: Configure Git to Use Wrapper

**File:** `.gitconfig` (in repository root)

```ini
[alias]
  # Override 'git commit' with wrapper that blocks --no-verify
  commit = !bash .git/hooks/commit-wrapper.sh

  # Emergency override for HUMAN use only
  commit-force-override = commit --no-verify
```

### Step 4: Activate for Repository

```powershell
git config --local include.path ../.gitconfig
```

**Now:**
- ✅ `git commit -m "..."` → Uses wrapper (blocks --no-verify)
- ❌ `git commit --no-verify` → Blocked with error message
- 🚨 `git commit-force-override -m "..."` → Emergency human override (logged in docs)

---

## Solution 2: Custom Git Hook (Server-Side)

If using a Git server (GitHub, GitLab, Gitea), add **server-side pre-receive hook**.

**File:** `.git/hooks/pre-receive` (on Git server)

```bash
#!/bin/bash
# Server-side hook - cannot be bypassed by --no-verify

while read oldrev newrev refname; do
  # Get list of commits being pushed
  commits=$(git rev-list $oldrev..$newrev)
  
  for commit in $commits; do
    # Check if commit message contains bypass marker
    message=$(git log -1 --pretty=%B $commit)
    
    if [[ "$message" == *"--no-verify"* ]]; then
      echo "❌ PUSH REJECTED: Commit $commit was created with --no-verify"
      echo "This is strictly forbidden. Please fix locally and force-push."
      exit 1
    fi
  done
done

exit 0
```

**Limitation:** Only works if you control the Git server.

---

## Solution 3: VS Code Extension Settings

Restrict Git operations in VS Code for AI agents.

**File:** `.vscode/settings.json`

```json
{
  "git.allowNoVerifyCommit": false,
  "git.confirmNoVerifyCommit": true,
  
  "github.copilot.chat.allowCommitWithoutHooks": false,
  "github.copilot.chat.requireTestsBeforeCommit": true
}
```

**Limitation:** VS Code AI agents may not respect these settings (experimental).

---

## Solution 4: PowerShell Function Override (Windows)

Add to `$PROFILE` (PowerShell profile):

**File:** `C:\Users\<YourUser>\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`

```powershell
# Override git command to block --no-verify
function git {
    $args_string = $args -join ' '
    
    # Check if commit command contains --no-verify
    if ($args[0] -eq 'commit' -and ($args_string -like '*--no-verify*' -or $args_string -like '*-n *')) {
        Write-Host "❌ ERROR: --no-verify is STRICTLY FORBIDDEN" -ForegroundColor Red
        Write-Host ""
        Write-Host "Pre-commit hooks ensure:"
        Write-Host "  - All tests pass (Backend + Frontend + E2E)"
        Write-Host "  - Code is formatted and linted"
        Write-Host "  - Security checks pass"
        Write-Host ""
        Write-Host "If hooks fail: Fix the problem, don't bypass!"
        Write-Host ""
        Write-Host "Emergency override: git-real commit --no-verify (HUMANS ONLY)"
        return
    }
    
    # Normal git command
    & "C:\Program Files\Git\bin\git.exe" @args
}

# Alias for emergency human override
function git-real {
    & "C:\Program Files\Git\bin\git.exe" @args
}
```

**Reload Profile:**
```powershell
. $PROFILE
```

**Now in PowerShell:**
- ✅ `git commit -m "..."` → Allowed
- ❌ `git commit --no-verify` → Blocked
- 🚨 `git-real commit --no-verify` → Emergency override

---

## Solution 5: Pre-Commit Hook Enhancement (Already Implemented)

The `.pre-commit-config.yaml` now includes:

```yaml
- id: all-tests-must-pass
  name: "🚨 MANDATORY: Run ALL tests - 100% must pass"
  entry: bash -c 'npm test'
  language: system
  pass_filenames: false
  always_run: true
  stages: [pre-commit]
```

**This hook:**
- Runs on EVERY commit attempt
- Executes full test suite (Backend + Frontend + E2E)
- Blocks commit if ANY test fails
- Can be bypassed by `--no-verify` ⚠️ (hence need for solutions above)

---

## Recommended Configuration (Layered Defense)

**Layer 1:** Pre-commit hook (catches 99% of issues)  
**Layer 2:** PowerShell function override (blocks --no-verify in terminal)  
**Layer 3:** Git alias wrapper (blocks --no-verify in Git directly)  
**Layer 4:** Server-side hook (final safety net)

**Apply ALL layers** for maximum protection against accidental bypasses.

---

## Emergency Override Procedure (Human Only)

If you **absolutely must** commit without hooks (e.g., fixing broken hooks):

1. **Document reason** in commit message:
   ```bash
   git commit-force-override -m "fix(hooks): repair broken pre-commit hook
   
   EMERGENCY OVERRIDE REASON: Pre-commit hook itself is broken and prevents all commits.
   This commit fixes the hook. Tests verified manually."
   ```

2. **Log in team chat** that override was used
3. **Fix issue immediately** in next commit
4. **Never use for "tests are failing"** - fix tests instead!

---

## Detection: How to Check if --no-verify Was Used

**Check recent commits:**
```bash
# Show commits that bypassed hooks (heuristic - checks for missing hook markers)
git log --all --oneline --no-merges | head -20
```

**Verify commit has hook signatures:**
```bash
# Pre-commit hooks should have added formatting changes
git show <commit-hash> --stat | grep -E "(black|prettier|ruff)"
```

**If commit lacks hook evidence:**
- Likely bypassed with `--no-verify`
- Investigate with `git log -p <commit-hash>`

---

## Summary

| Solution | Effectiveness | Complexity | Recommended |
|----------|--------------|------------|-------------|
| 1. Git Alias Wrapper | 🟢 High | Medium | ✅ Yes |
| 2. Server-Side Hook | 🟢 Perfect | High | ✅ If you control server |
| 3. VS Code Settings | 🟡 Experimental | Low | ⚠️ Uncertain |
| 4. PowerShell Override | 🟢 High | Low | ✅ Yes (Windows) |
| 5. Pre-Commit Hook | 🟡 Medium | Low | ✅ Already done |

**⚠️ CRITICAL:** Even with all layers, determined humans can still bypass (by editing scripts). The goal is:
1. **Prevent accidental bypasses** (especially by AI agents)
2. **Make intentional bypasses obvious** (logged, documented)
3. **Educate team** that bypassing hooks is serious policy violation

---

## Enforcement in AGENTS.md

Add to `AGENTS.md`:

```markdown
### GIT COMMITS - ABSOLUTE PROHIBITIONS

**❌ VERBOTEN - NEVER USE:**
```bash
git commit --no-verify
git commit -n
```

**Why:** Pre-commit hooks enforce test quality. Bypassing = broken commits.

**If hooks fail:**
1. Fix the actual problem (failing tests, format errors)
2. Do NOT look for workarounds
3. Do NOT use --no-verify

**Consequence:** Commits bypassing hooks will be reverted immediately.
```

---

**Last Updated:** 2026-02-13  
**Enforcement Level:** 🔴 CRITICAL - Zero tolerance for violations
