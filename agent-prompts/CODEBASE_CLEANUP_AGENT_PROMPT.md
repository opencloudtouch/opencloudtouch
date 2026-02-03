# 🧹 CloudTouch Codebase & Documentation Cleanup - Agent Instructions

**Project**: CloudTouch (Bose SoundTouch Bridge)  
**Objective**: Eliminate technical debt, remove workarounds, consolidate documentation, achieve clean architecture  
**Execution**: Sequential phases with quality gates  
**Version**: 2026-02-03

---

## 📋 MISSION OVERVIEW

After extensive refactoring iterations, the codebase contains:
- ❌ Workarounds that treat symptoms instead of root causes
- ❌ Overly complex solutions from incremental problem-solving
- ❌ Deviations from standard practices (React, FastAPI, pytest best practices)
- ❌ Technical debt from rapid prototyping
- ❌ Verbose documentation with outdated information
- ❌ Duplicated or conflicting documentation

**GOAL**: Production-ready codebase with minimal complexity, clean architecture, and concise documentation.

---

## ⚙️ AUTONOMY PROTOCOL

**⚠️ CRITICAL: Execute ALL cleanup tasks completely autonomously without user interruption.**

### Default Mode: AUTONOMOUS EXECUTION

**RULE #1: DO NOT ASK, EXECUTE**
- ALL analysis and cleanup tasks MUST be executed autonomously
- NO permission requests before removing code/docs
- NO status updates asking "should I continue?"
- NO confirmation requests for standard cleanup operations
- Agent analyzes, executes, validates, and proceeds to next phase

**RULE #2: User decisions ONLY for these exceptions**:
1. ❌ **Complete class deletion** (entire class removed from codebase)
   - ✅ AUTONOMOUS: Removing dead code within classes
   - ✅ AUTONOMOUS: Removing unused methods, properties, imports
   - ✅ AUTONOMOUS: Refactoring, renaming, restructuring classes
   - ❌ USER DECISION: Deleting entire class file (e.g., `UserService.py` completely removed)

2. ❌ **Documentation deletion** (entire document removed)
   - ✅ AUTONOMOUS: Consolidating 5 READMEs into 1 comprehensive README
   - ✅ AUTONOMOUS: Removing outdated sections from docs
   - ✅ AUTONOMOUS: Rewriting verbose docs to be concise
   - ✅ AUTONOMOUS: Merging duplicate documentation
   - ❌ USER DECISION: Deleting entire README/guide (e.g., `docs/DEPLOYMENT.md` removed, not merged)

**RULE #3: Deferred Decision Pattern**

If a USER DECISION is needed but NOT blocking current cleanup:
1. **Document the decision** in `docs/analysis/pending-decisions.md`:
   ```markdown
   ### [Cleanup Task] - [Decision Title]
   **Context**: [Why this needs user decision]
   **Impact**: [What happens if we delete vs. keep]
   **Recommendation**: [Agent's recommendation with rationale]
   **Blocked Tasks**: [List of tasks that cannot proceed without this decision]
   **Status**: PENDING
   ```

2. **Continue with other cleanup tasks** that don't require the decision
3. **Check before each new phase**: Does this phase require a pending decision?
   - YES → Skip phase, document in blocked tasks
   - NO → Execute phase autonomously

**RULE #4: NO EXCUSES FOR CLEANUP**

The following are **NOT valid reasons** to interrupt user:
- ❌ "This removes a lot of code" → GOOD (Less code = better)
- ❌ "Not sure if this is used" → CHECK (grep_search, list_code_usages)
- ❌ "Multiple docs mention this" → FIX ALL (Use multi_replace)
- ❌ "Complex consolidation" → DO IT (Create comprehensive doc)
- ❌ "Tests might need updates" → UPDATE THEM (TDD required)
- ❌ "Large diff" → EXPECTED (Cleanup creates large diffs)
- ❌ "Want to confirm deletion" → NO (Use tools to verify, then delete)

**RULE #5: Validation Before Deletion (Automated)**

Before deleting ANY code:
1. Run `grep_search` to find all references
2. Run `list_code_usages` for functions/classes
3. Check imports with semantic_search
4. If NO references found → Delete autonomously
5. If references exist:
   - Dead code (only tests/mocks reference it) → Delete autonomously + update tests
   - Real usage → Refactor to remove dependency, THEN delete
6. Run full test suite after deletion
7. If tests fail → Fix immediately (no user escalation)

**RULE #6: Documentation Consolidation (Autonomous)**

Example autonomous consolidation:
```markdown
BEFORE:
- docs/DEPLOYMENT.md (50 lines, outdated)
- docs/DOCKER.md (30 lines, overlaps with DEPLOYMENT.md)
- deployment/README.md (40 lines, duplicate info)
- SERVER-DEPLOY.md (60 lines, NAS Server-specific)

AFTER (AUTONOMOUS):
- docs/DEPLOYMENT.md (80 lines, comprehensive, includes all scenarios)
- SERVER-DEPLOY.md (kept, references DEPLOYMENT.md for common steps)
- DELETE: docs/DOCKER.md (merged into DEPLOYMENT.md)
- DELETE: deployment/README.md (merged into DEPLOYMENT.md)

Agent consolidates WITHOUT asking because:
- ✅ No complete doc deletion (DOCKER.md content preserved in DEPLOYMENT.md)
- ✅ Information preserved (consolidated, not lost)
- ✅ Improves clarity (single source of truth)
```

**RULE #7: Commit Strategy (When Instructed)**

Per AGENTS.md, commits ONLY on explicit user instruction.
BUT within a cleanup session:
- ✅ Execute entire phase (20-50 file changes)
- ✅ Keep all tests green throughout
- ✅ Build cohesive cleanup changeset
- ❌ Stop after each file asking "commit now?"

User will decide when to commit after reviewing cleanup scope.

**ENFORCEMENT**:

Example violations vs. correct behavior:

❌ **VIOLATION**: "I found 5 unused imports in `utils.py`. Should I remove them?"
✅ **CORRECT**: Removes unused imports, runs tests, proceeds to next file.

❌ **VIOLATION**: "There are 3 README files with overlapping content. Should I consolidate?"
✅ **CORRECT**: Consolidates into 1 comprehensive README, deletes redundant sections (not entire files), updates cross-references.

❌ **VIOLATION**: "Class `LegacyAdapter` seems unused. Confirm deletion?"
✅ **CORRECT**: Runs grep_search + list_code_usages, finds no references except deprecated tests, deletes class + tests, runs test suite, proceeds.

**Autonomy Checklist (Before ANY user interaction)**:
- [ ] Am I deleting an ENTIRE class file? (If NO → Don't ask)
- [ ] Am I deleting an ENTIRE documentation file? (If NO → Don't ask)
- [ ] Is there a technical blocker? (If NO → Don't ask)
- [ ] Can I defer this decision? (If YES → Defer and continue)
- [ ] Did I validate with grep_search/list_code_usages? (Must be YES before deleting)

**If all checks pass → EXECUTE AUTONOMOUSLY, DO NOT ASK.**

---

## 🎯 PHASE 0: CONTEXT ACQUISITION (30 minutes)

**⚠️ CRITICAL: Real Device Tests are EXCLUDED from all automated runs!**

**Real vs. Mock Tests**:
- **Mock Tests**: Run by default (unit, integration, E2E with mock adapters)
- **Real Tests**: NEVER run automatically (require physical Bose SoundTouch hardware)
- **Separation**: Real tests marked with `@pytest.mark.real_devices` or in `tests/real/` directories
- **Execution**: Only via explicit scripts (`scripts/run-real-tests.ps1`)

**Validation**:
```powershell
# Check pytest.ini excludes real tests by default
cat backend/pytest.ini | Select-String "addopts.*not real_devices"

# Check pre-commit hook doesn't run real tests
cat pre-commit.ps1 | Select-String "real"  # Should find NO reference to real tests

# Verify real test markers
Get-ChildItem backend/tests/real/*.py | ForEach-Object { 
  Get-Content $_ | Select-String "pytestmark.*real_devices" 
}
```

**If violations found**:
- ❌ Real tests in default test run → Fix pytest.ini addopts
- ❌ Pre-commit hook runs real tests → Remove from hook
- ❌ Real tests not marked → Add `pytestmark = pytest.mark.real_devices`

### 0.1 Understand Application Purpose via Cypress E2E Tests

**Action**: Analyze Cypress test scenarios to extract:
- Core user workflows
- Business logic flow
- Feature set (device discovery, playback control, preset management, radio browsing)
- Integration points (Backend API, SoundTouch devices, RadioBrowser)

**Deliverable**: Temporary context document (1 page max):
```markdown
# CloudTouch - Application Context (TEMP)

## Purpose
[1 sentence: What does CloudTouch do?]

## User Workflows (from Cypress tests)
1. Device Discovery: [2-3 sentences]
2. Playback Control: [2-3 sentences]
3. Preset Management: [2-3 sentences]
4. Radio Browsing: [2-3 sentences]

## Technical Stack
- Frontend: [React version, key libraries]
- Backend: [FastAPI version, key dependencies]
- Testing: [Cypress, pytest, vitest versions]

## Architecture (from tests)
- API Endpoints: [list critical endpoints]
- State Management: [Redux/Context/other]
- External Services: [SoundTouch API, RadioBrowser API]
```

**Files to analyze**:
- `frontend/cypress/e2e/**/*.cy.js`
- `frontend/cypress/support/commands.js`
- `backend/tests/e2e/**/*.py`

---

## 🔍 PHASE 1: FRONTEND CODE ANALYSIS (60 minutes)

### 1.1 Static Code Analysis

**Tools to run**:
```powershell
# ESLint (JavaScript/React linting)
cd frontend
npm run lint -- --format json --output-file ../analysis/eslint-report.json

# Prettier (code formatting violations)
npx prettier --check "src/**/*.{js,jsx,css}" --write=false > ../analysis/prettier-violations.txt

# Dependency audit (security vulnerabilities)
npm audit --json > ../analysis/npm-audit.json

# Bundle size analysis
npm run build -- --mode production
npx vite-bundle-visualizer --analyze dist/stats.json > ../analysis/bundle-size.txt

# Dead code detection
npx unimported --init
npx unimported > ../analysis/dead-code.txt

# Cyclomatic complexity (React components)
npx es6-plato -r -d ../analysis/complexity-report src/
```

### 1.2 Manual Code Review Checklist

**Architecture Violations**:
- [ ] Are components doing too much? (>200 lines = suspect)
- [ ] Is state management consistent? (Redux vs. Context vs. local useState)
- [ ] Are side effects properly handled? (useEffect dependencies correct?)
- [ ] Is data fetching centralized? (API layer vs. scattered fetch calls)
- [ ] Are PropTypes/TypeScript used consistently?

**React Best Practices Violations**:
- [ ] Unnecessary re-renders (missing React.memo, useMemo, useCallback)?
- [ ] Keys in lists (using index as key)?
- [ ] Event handler naming (handleClick vs. onClick)?
- [ ] Conditional rendering (ternary hell vs. early returns)?
- [ ] Inline function definitions in JSX (performance issue)?

**Code Smells**:
- [ ] Magic numbers/strings (should be constants)
- [ ] Copy-pasted code (DRY violations)
- [ ] Commented-out code (delete it!)
- [ ] Console.log statements in production code
- [ ] Try-catch without proper error handling
- [ ] Empty catch blocks (error swallowing)

**Workarounds & Hacks**:
- [ ] setTimeout/setInterval for race condition fixes (symptom, not root cause)
- [ ] Multiple useEffect calls doing related things (should be one)
- [ ] Force re-renders (key={Date.now()}) - WHY?
- [ ] Prop drilling >3 levels (use Context/Redux)
- [ ] Duplicate API calls (caching missing?)

**File Structure Issues**:
- [ ] Files in wrong directories (`utils/` containing components?)
- [ ] Inconsistent naming (camelCase vs. PascalCase)
- [ ] Missing index.js for barrel exports
- [ ] Too many files in one directory (>20 = needs subdirectories)

### 1.3 Dependencies Audit

**Check for**:
- Unused dependencies (from `unimported` output)
- Outdated dependencies (run `npm outdated`)
- Duplicate dependencies (multiple versions of same lib)
- Unnecessary polyfills (if targeting modern browsers)
- Heavy libraries for simple tasks (lodash for one function?)

**Document**:
```markdown
| Dependency | Current Version | Latest | Used? | Action |
|------------|-----------------|--------|-------|--------|
| react-router-dom | 6.x | 6.y | ✅ | Keep |
| lodash | 4.17.21 | 4.17.21 | ❌ | REMOVE (only using _.debounce, replace with custom) |
```

### 1.4 Deliverable: Frontend Analysis Report

**Format** (max 3 pages):
```markdown
# Frontend Code Analysis Report

## Executive Summary
- Total Issues Found: [number]
- Critical: [number] (blocking production)
- High: [number] (should fix)
- Medium: [number] (nice to have)
- Low: [number] (cosmetic)

## Critical Issues (MUST FIX)
### Issue 1: [Title]
- **Location**: `src/components/DeviceList.jsx:45-67`
- **Problem**: Using setTimeout to fix race condition in device discovery
- **Root Cause**: Missing dependency in useEffect
- **Fix**: Add `devices` to dependency array, remove setTimeout
- **Files Affected**: 1
- **Estimated Effort**: 15 minutes

## High Priority Issues (SHOULD FIX)
[Same format as Critical]

## Code Cleanup Opportunities
- Remove dead code: [list files]
- Consolidate duplicates: [list patterns]
- Extract components: [list candidates]

## Dependencies
- Remove: [list]
- Update: [list]
- Security fixes: [list from npm audit]

## Metrics
- Lines of Code: [total]
- Cyclomatic Complexity: [average, max]
- Bundle Size: [KB]
- Test Coverage: [%]
```

---

## 🔍 PHASE 2: BACKEND CODE ANALYSIS (60 minutes)

### 2.1 Static Code Analysis

**Tools to run**:
```powershell
cd backend

# Ruff (fast Python linter)
ruff check src/ tests/ --output-format json > ../analysis/ruff-report.json

# Black (code formatting)
black --check --diff src/ tests/ > ../analysis/black-violations.txt

# MyPy (type checking)
mypy src/ --strict --no-error-summary --json-report ../analysis/mypy-report

# Bandit (security issues)
bandit -r src/ -f json -o ../analysis/bandit-security.json

# Radon (cyclomatic complexity)
radon cc src/ -a -s -j > ../analysis/radon-complexity.json

# Vulture (dead code detection)
vulture src/ > ../analysis/dead-code-backend.txt

# Safety (dependency vulnerabilities)
safety check --json > ../analysis/safety-report.json

# Import analysis (circular imports, unused imports)
pylint src/ --disable=all --enable=cyclic-import,unused-import --output-format=json > ../analysis/import-issues.json
```

### 2.2 Manual Code Review Checklist

**Clean Architecture Violations**:
- [ ] Are layers properly separated? (API → Use Cases → Domain → Adapters → Infrastructure)
- [ ] Dependencies flowing inward? (outer layers depend on inner, not vice versa)
- [ ] Domain models free of infrastructure concerns? (no SQLAlchemy in domain)
- [ ] Adapters wrapping external systems? (SoundTouch, RadioBrowser)
- [ ] Repository pattern used consistently for data access?

**FastAPI Best Practices Violations**:
- [ ] Dependency injection used properly? (Depends() for shared resources)
- [ ] Request validation with Pydantic models?
- [ ] Response models defined (not returning raw dicts)?
- [ ] HTTP status codes correct (201 for creation, 204 for deletion)?
- [ ] Error handling with HTTPException?
- [ ] Background tasks for long operations?
- [ ] API versioning strategy (/api/v1/)?

**Python Code Smells**:
- [ ] God classes (>300 lines, doing too much)
- [ ] Long functions (>50 lines)
- [ ] Too many parameters (>4 = use dataclass)
- [ ] Mutable default arguments (`def func(items=[])`)?
- [ ] Bare except clauses (`except:` without exception type)
- [ ] Global variables (except constants)
- [ ] String concatenation in loops (use f-strings or join)
- [ ] Import * (from module import *)

**Async/Await Issues**:
- [ ] Blocking I/O in async functions (requests instead of httpx)
- [ ] Missing await on async calls
- [ ] Unnecessary async (function doesn't do I/O)
- [ ] Mixing sync and async code incorrectly

**Workarounds & Hacks**:
- [ ] Sleep/delay to avoid race conditions (symptom fix)
- [ ] Try-except to hide errors (proper error handling?)
- [ ] Hardcoded timeouts (should be configurable)
- [ ] Duplicate code (extract to utils/shared modules)

**Configuration Issues**:
- [ ] Hardcoded values (should be in config/env vars)
- [ ] Secrets in code (use environment variables)
- [ ] Config scattered across files (centralize in config.py)
- [ ] No validation of config values (Pydantic Settings)

### 2.3 Dependencies Audit

**Check for**:
- Unused dependencies (from vulture output)
- Outdated dependencies (`pip list --outdated`)
- Conflicting versions in requirements.txt vs pyproject.toml
- Missing version pins (should pin all dependencies)
- Development dependencies in production requirements

**Document**:
```markdown
| Dependency | Current | Latest | Used? | Action |
|------------|---------|--------|-------|--------|
| httpx | 0.24.1 | 0.27.0 | ✅ | UPDATE |
| libsoundtouch | local | N/A | ✅ | Keep |
| pytest-mock | 3.11.1 | 3.12.0 | ❌ | REMOVE (not used, using unittest.mock) |
```

### 2.4 Security & Vulnerabilities Analysis

**⚠️ CRITICAL**: Security is NOT optional. Every vulnerability must be addressed before production deployment.

#### 2.4.1 Dependency Vulnerability Scanning

**Backend (Python)**:
```powershell
cd backend

# Safety - Check for known security vulnerabilities in dependencies
safety check --json --output ../analysis/safety-vulnerabilities.json
safety check --full-report > ../analysis/safety-full-report.txt

# Pip-audit - Alternative vulnerability scanner (more up-to-date)
pip-audit --format json --output ../analysis/pip-audit.json
pip-audit --desc > ../analysis/pip-audit-detailed.txt

# Bandit - Security issue scanner for Python code
bandit -r src/ -f json -o ../analysis/bandit-security.json
bandit -r src/ -ll -i  # Show only medium/high severity issues

# Check for outdated dependencies with known CVEs
pip list --outdated --format json > ../analysis/outdated-packages.json
```

**Frontend (JavaScript/TypeScript)**:
```powershell
cd frontend

# npm audit - Built-in vulnerability scanner
npm audit --json > ../analysis/npm-audit.json
npm audit --audit-level=moderate > ../analysis/npm-audit-summary.txt

# Audit production dependencies only (ignore devDependencies)
npm audit --production --json > ../analysis/npm-audit-production.json

# Check for outdated packages with security updates
npm outdated --json > ../analysis/npm-outdated.json

# Snyk (if available) - Alternative vulnerability scanner
npx snyk test --json > ../analysis/snyk-report.json || echo "Snyk not configured"
```

#### 2.4.2 Security Checklist - Backend

**Critical Security Issues** (MUST FIX before production):
- [ ] **Secrets in Code**: No API keys, passwords, tokens in source files
- [ ] **SQL Injection**: Using parameterized queries (FastAPI + SQLAlchemy = safe)
- [ ] **Command Injection**: No `os.system()`, `subprocess.shell=True` with user input
- [ ] **Path Traversal**: Validate file paths, use `os.path.abspath()` and check within allowed directory
- [ ] **CORS Configuration**: Not allowing `*` in production (specific origins only)
- [ ] **Authentication**: Protected endpoints have proper auth (if applicable)
- [ ] **Input Validation**: All user inputs validated with Pydantic models
- [ ] **Error Messages**: No stack traces/internal info leaked to clients
- [ ] **Dependency Vulnerabilities**: All HIGH/CRITICAL CVEs patched

**High Priority Security Issues** (Fix ASAP):
- [ ] **Rate Limiting**: Prevent DoS attacks on discovery/API endpoints
- [ ] **HTTPS Only**: Ensure production deployment uses TLS/SSL
- [ ] **Environment Variables**: Sensitive config from `.env`, not hardcoded
- [ ] **Logging**: No sensitive data logged (passwords, tokens, IP addresses in plain text)
- [ ] **File Uploads**: If accepting files, validate type/size/content
- [ ] **XML Parsing**: Using safe XML parsers (defusedxml) to prevent XXE attacks
- [ ] **Deserialization**: No `pickle.loads()` on untrusted data
- [ ] **Regex DoS**: No catastrophic backtracking in regex patterns

**Medium Priority Security Issues**:
- [ ] **Debug Mode**: Disabled in production (`CT_LOG_LEVEL != DEBUG`)
- [ ] **Directory Listing**: Web server doesn't expose directory listings
- [ ] **Version Disclosure**: Server headers don't reveal software versions
- [ ] **Session Management**: Secure cookie flags (HttpOnly, Secure, SameSite)
- [ ] **Dependency Pinning**: Exact versions pinned to prevent supply chain attacks
- [ ] **Subprocess Calls**: Use list syntax instead of shell strings

**Bandit High-Severity Patterns to Check**:
```python
# ❌ CRITICAL: Hardcoded password
PASSWORD = "admin123"  # Bandit: B105

# ❌ CRITICAL: SQL injection risk
query = f"SELECT * FROM users WHERE id = {user_id}"  # Bandit: B608

# ❌ HIGH: Command injection
os.system(f"ping {user_input}")  # Bandit: B605

# ❌ HIGH: Insecure random
import random
token = random.randint(1000, 9999)  # Bandit: B311 - Use secrets module

# ❌ MEDIUM: Unsafe YAML load
yaml.load(data)  # Bandit: B506 - Use yaml.safe_load()

# ✅ CORRECT: Safe alternatives
from secrets import token_urlsafe
PASSWORD = os.getenv("CT_ADMIN_PASSWORD")  # From environment
query = "SELECT * FROM users WHERE id = ?"  # Parameterized
subprocess.run(["ping", user_input], check=True)  # List syntax
token = token_urlsafe(16)  # Cryptographically secure
yaml.safe_load(data)  # Safe YAML parsing
```

#### 2.4.3 Security Checklist - Frontend

**Critical Security Issues**:
- [ ] **XSS (Cross-Site Scripting)**: React escapes by default, but check:
  - No `dangerouslySetInnerHTML` without sanitization (use DOMPurify)
  - No `eval()` or `new Function()` with user input
  - No `innerHTML` / `outerHTML` with user data
- [ ] **Sensitive Data Exposure**: No API keys, secrets in frontend code
- [ ] **Local Storage**: No sensitive data in localStorage/sessionStorage (tokens only in httpOnly cookies)
- [ ] **CSRF Protection**: API calls include CSRF tokens if using cookies
- [ ] **Content Security Policy**: CSP headers configured on backend
- [ ] **Dependency Vulnerabilities**: All HIGH/CRITICAL npm audit issues resolved

**High Priority Security Issues**:
- [ ] **Input Sanitization**: User input sanitized before rendering
- [ ] **URL Validation**: External links validated, no `javascript:` URLs
- [ ] **Iframe Security**: If using iframes, proper `sandbox` attributes
- [ ] **PostMessage**: If using `window.postMessage`, origin validated
- [ ] **Third-Party Scripts**: Minimal use, loaded from trusted CDNs with SRI
- [ ] **Console Logging**: No sensitive data in `console.log()` (remove in production)

**Common Frontend Vulnerabilities**:
```javascript
// ❌ CRITICAL: XSS vulnerability
<div dangerouslySetInnerHTML={{ __html: userInput }} />

// ❌ CRITICAL: Hardcoded API key
const API_KEY = "sk-proj-abc123..."  // NEVER do this!

// ❌ HIGH: Sensitive data in localStorage
localStorage.setItem('password', password)  // Accessible via XSS

// ❌ MEDIUM: Unvalidated redirect
window.location = userInput  // Can redirect to malicious site

// ✅ CORRECT: Safe alternatives
import DOMPurify from 'dompurify'
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userInput) }} />

const API_KEY = import.meta.env.VITE_API_KEY  // From .env, backend validation

// Use httpOnly cookies for auth tokens (set by backend)
// localStorage only for non-sensitive UI state

// Validate redirect URL
const allowedDomains = ['system.local']
if (allowedDomains.some(d => url.includes(d))) window.location = url
```

#### 2.4.4 Outdated Dependencies Risk Assessment

**Priority Levels for Updates**:

| Severity | CVE Score | Action | Timeline |
|----------|-----------|--------|----------|
| CRITICAL | 9.0-10.0 | Update IMMEDIATELY | Same day |
| HIGH | 7.0-8.9 | Update within 1 week | < 7 days |
| MEDIUM | 4.0-6.9 | Update within 1 month | < 30 days |
| LOW | 0.1-3.9 | Update next release | Next version |
| None | N/A (just outdated) | Evaluate benefit vs. risk | As needed |

**Dependency Update Strategy**:
1. **Check Release Notes**: What changed? Breaking changes?
2. **Test in Dev**: Update locally, run full test suite
3. **Check Transitive Dependencies**: Does update pull in vulnerable sub-dependencies?
4. **One at a time**: Update ONE major dependency per commit (easier rollback)
5. **Pin Versions**: After update, pin exact version in requirements.txt / package-lock.json

**Example Analysis**:
```markdown
| Package | Current | Latest | CVE | Severity | Action | Blocked By |
|---------|---------|--------|-----|----------|--------|------------|
| httpx | 0.24.1 | 0.27.0 | CVE-2024-XXXX | HIGH | UPDATE | None |
| fastapi | 0.100.0 | 0.110.0 | None | - | UPDATE | Tests pass ✅ |
| pillow | 9.0.0 | 10.2.0 | CVE-2023-XXXX | CRITICAL | UPDATE NOW | ⚠️ Breaking changes in 10.x |
| pytest | 7.4.0 | 8.0.0 | None | - | WAIT | Breaking changes, low priority |
| lodash | 4.17.20 | 4.17.21 | CVE-2021-23337 | HIGH | REMOVE | Not used anymore |
```

#### 2.4.5 Supply Chain Security

**npm/pip Package Integrity**:
- [ ] Verify package signatures where available
- [ ] Check package maintainer trustworthiness (GitHub stars, download count, last update)
- [ ] Review dependencies of dependencies (transitive vulnerabilities)
- [ ] Use `npm ci` instead of `npm install` (respects package-lock.json exactly)
- [ ] Use `pip-tools` or `poetry` for deterministic builds

**Suspicious Package Patterns** (🚨 RED FLAGS):
- ❌ Package name typosquatting (`reqeusts` instead of `requests`)
- ❌ Package with 0 downloads, created yesterday
- ❌ Package pulling in 50+ dependencies for simple task
- ❌ Maintainer email from sketchy domain
- ❌ Package requesting unusual permissions (network access for a date formatter?)

**Lock File Validation**:
```powershell
# Verify npm lockfile integrity
npm audit fix  # Auto-fix non-breaking updates
npm audit fix --force  # ⚠️ May introduce breaking changes

# Verify pip dependencies match lockfile
pip check  # Check for conflicts
pip freeze > requirements.lock.txt  # Generate exact versions
diff requirements.txt requirements.lock.txt  # Compare
```

#### 2.4.6 Deliverable: Security Audit Report

**Format** (max 2 pages):
```markdown
# Security Audit Report - CloudTouch Backend

## Executive Summary
- **Critical Vulnerabilities**: [N] found, [N] fixed, [N] remaining
- **High Vulnerabilities**: [N] found, [N] fixed, [N] remaining
- **Medium/Low**: [N] (acceptable risk)
- **Overall Risk Level**: [LOW/MEDIUM/HIGH/CRITICAL]

## Critical Issues Requiring Immediate Action

### 1. [CVE-YYYY-XXXXX] - Pillow Remote Code Execution
- **Package**: pillow 9.0.0
- **Severity**: CRITICAL (CVSS 9.8)
- **Impact**: Arbitrary code execution via malicious image
- **Fix**: Update to pillow >= 10.2.0
- **Status**: ❌ NOT FIXED (breaking changes in 10.x)
- **Action Plan**: 
  1. Review Pillow API changes (1 hour)
  2. Update code for v10 compatibility (2 hours)
  3. Test image processing flows (1 hour)
  4. Deploy ASAP

### 2. [Bandit B105] - Hardcoded Password in config.py
- **File**: `src/cloudtouch/core/config.py:45`
- **Issue**: `DEFAULT_PASSWORD = "admin123"`
- **Severity**: CRITICAL
- **Fix**: Move to environment variable `CT_ADMIN_PASSWORD`
- **Status**: ✅ FIXED in commit abc123f
- **Verification**: Manually tested, no hardcoded secrets remain

## High Priority Issues (Fix within 7 days)

[List each issue with same format as Critical]

## Dependency Vulnerabilities Summary

| Package | Current | Latest | CVE | Severity | Status |
|---------|---------|--------|-----|----------|--------|
| httpx | 0.24.1 | 0.27.0 | CVE-2024-12345 | HIGH | ⏳ Update in progress |
| pillow | 9.0.0 | 10.2.0 | CVE-2023-98765 | CRITICAL | ❌ Blocked by breaking changes |
| fastapi | 0.100.0 | 0.110.0 | None | - | ✅ Updated |

## Bandit Security Scan Results
- **Total Issues**: [N]
- **High Severity**: [N]
- **Medium Severity**: [N]
- **Low Severity**: [N]
- **False Positives**: [N] (document why)

## Recommendations
1. **Immediate**: Fix all CRITICAL issues (ETA: [date])
2. **Short-term**: Fix HIGH issues (ETA: [date])
3. **Ongoing**: Monitor dependency updates monthly
4. **Process**: Add security scanning to CI/CD pipeline

## Risk Acceptance (if any)
- **Issue**: [Description]
- **Reason**: [Why not fixing now]
- **Mitigation**: [What we're doing instead]
- **Review Date**: [When to re-evaluate]
```

### 2.5 Performance Analysis

**Objective**: Measure and optimize performance across ALL execution contexts (runtime, build, test, deployment).

**Performance Categories**:

#### 2.5.1 Application Runtime Performance

**Backend API Performance**:
```powershell
# Measure API endpoint response times
cd backend
pytest tests/performance/ --benchmark-only --benchmark-json=../analysis/api-benchmarks.json

# Monitor in production (if deployed)
# Check logs for slow requests >100ms
Get-Content data-local/cloudtouch.log | Select-String "duration" | 
  Where-Object { $_ -match "duration.*([0-9]{3,}ms)" }
```

**Frontend Performance**:
```powershell
# Lighthouse CI performance score
cd frontend
npm install -g @lhci/cli
lhci autorun --collect.url=http://localhost:4173

# Bundle size analysis
npm run build -- --profile
npx vite-bundle-visualizer
```

**Performance Targets**:
- API Response Time: p95 <100ms, p99 <500ms
- Time to Interactive (TTI): <3s
- First Contentful Paint (FCP): <1.5s
- Bundle Size: <500KB gzipped
- Lighthouse Score: >90 (Performance)

**Common Bottlenecks**:
- Synchronous SSDP discovery (should be async)
- N+1 database queries (use batch loading)
- Large JSON payloads (use pagination)
- Missing caching (HTTP headers, in-memory cache)
- Unoptimized images (use WebP, lazy loading)

#### 2.5.2 Build Performance

**Targets**:
- Frontend Build (Vite): <30s
- Backend Build (pip install): <60s
- Docker Build (multi-stage): <3min
- Docker Image Size: <500MB

**Measurement**:
```powershell
# Frontend build time
Measure-Command { cd frontend; npm run build }

# Backend dependencies install
Measure-Command { cd backend; pip install -r requirements.txt }

# Docker build time
Measure-Command { docker build -t cloudtouch:test . }

# Docker image size
docker images cloudtouch:test --format "{{.Size}}"
```

**Optimization Techniques**:
- Layer caching (COPY requirements.txt before COPY .)
- Multi-stage builds (builder → runtime)
- .dockerignore (exclude node_modules/, .venv/, htmlcov/)
- Dependency pinning (avoid unnecessary rebuilds)
- Parallel builds (npm ci --legacy-peer-deps)

#### 2.5.3 Test Performance

**Targets**:
- Unit Tests (pytest): <10s total
- Unit Tests (vitest): <5s total
- Integration Tests: <30s total
- E2E Tests (Cypress): <60s total
- Pre-commit Hook: <2min total

**Measurement**:
```powershell
# Backend test duration
Measure-Command { cd backend; pytest -v --durations=10 }

# Frontend test duration
Measure-Command { cd frontend; npm run test:unit }

# E2E test duration
Measure-Command { cd frontend; npm run test:e2e:mock }

# Pre-commit hook total time
Measure-Command { .\pre-commit.ps1 }
```

**Optimization Techniques**:
- Parallel test execution (pytest-xdist: -n auto)
- Mock external services (no real HTTP calls in unit tests)
- Database fixtures (reuse DB setup across tests)
- Selective test runs (only changed modules)
- Test order optimization (fast tests first)

**Anti-Patterns**:
- ❌ Real API calls in unit tests (use mocks)
- ❌ Sleep/wait in tests (use proper async/await)
- ❌ Large test fixtures (generate minimal data)
- ❌ No test isolation (tests depend on each other)
- ❌ Running E2E on every file save (use unit tests)

#### 2.5.4 Deployment Script Performance

**Targets**:
- Local Build → Run: <2min
- NAS Server Deployment (deploy-to-server.ps1): <5min
- Container Startup: <10s

**Measurement**:
```powershell
# Local deployment
Measure-Command { .\deployment\deploy-local.ps1 }

# NAS Server deployment
Measure-Command { .\deployment\deploy-to-server.ps1 }

# Container startup time
docker run cloudtouch:latest &
Measure-Command { 
  do { Start-Sleep -Seconds 1 } 
  until (Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet)
}
```

**Optimization Techniques**:
- Incremental builds (don't rebuild if no changes)
- Parallel operations (build frontend + backend simultaneously)
- SSH connection reuse (ControlMaster for multiple commands)
- Image layer caching (don't invalidate layers unnecessarily)
- Health checks (don't wait fixed time, poll until ready)

#### 2.5.5 Performance Monitoring Tools

**Recommended Tools**:
```powershell
# Python profiling (cProfile for hotspots)
python -m cProfile -o profile.stats backend/main.py
python -m pstats profile.stats

# Memory profiling (memory_profiler)
pip install memory_profiler
python -m memory_profiler backend/main.py

# JavaScript profiling (Chrome DevTools)
# Open http://localhost:4173 in Chrome → F12 → Performance tab

# Docker stats (monitor container resources)
docker stats cloudtouch --no-stream

# Load testing (Locust for API stress testing)
pip install locust
locust -f tests/performance/locustfile.py
```

**Deliverable**: Performance baseline document
```markdown
# Performance Baseline (YYYY-MM-DD)

## Application Performance
- API p95: [X]ms (Target: <100ms)
- FCP: [X]s (Target: <1.5s)
- TTI: [X]s (Target: <3s)
- Lighthouse: [X]/100 (Target: >90)

## Build Performance
- Frontend Build: [X]s (Target: <30s)
- Docker Build: [X]s (Target: <180s)
- Image Size: [X]MB (Target: <500MB)

## Test Performance
- pytest: [X]s (Target: <10s)
- vitest: [X]s (Target: <5s)
- Cypress E2E: [X]s (Target: <60s)
- Pre-commit: [X]s (Target: <120s)

## Deployment Performance
- Local Deploy: [X]s (Target: <120s)
- NAS Server Deploy: [X]s (Target: <300s)
- Container Startup: [X]s (Target: <10s)

## Bottlenecks Identified
1. [Description] - Impact: [High/Medium/Low]
2. [Description] - Impact: [High/Medium/Low]

## Optimization Recommendations
1. [Recommendation] - Expected Gain: [X]%
2. [Recommendation] - Expected Gain: [X]%
```

**When to optimize**:
- ✅ Performance is <50% of target (e.g., API p95 >200ms)
- ✅ User-facing slowness (>3s load time)
- ✅ Build/test time impacts developer productivity (>5min pre-commit)
- ❌ Premature optimization (don't optimize before measuring)
- ❌ Micro-optimizations (100ms → 95ms is not worth complexity)

### 2.6 Deliverable: Backend Analysis Report

**Format** (max 3 pages, same structure as Frontend report)

---

## 🔍 PHASE 3: TEST SUITE ANALYSIS (60 minutes)

### 3.1 Frontend Tests (Vitest + Cypress)

**Static Analysis**:
```powershell
cd frontend

# Test coverage
npm run test:coverage -- --reporter=json > ../analysis/vitest-coverage.json

# Cypress test results
npx cypress run --reporter json > ../analysis/cypress-results.json

# Test file analysis (unused test files)
npx unimported --init --entry "tests/**/*.test.{js,jsx}"
```

**Manual Review Checklist**:
- [ ] Test coverage >80%? (check htmlcov/ or coverage report)
- [ ] Are tests testing implementation or behavior? (should be behavior)
- [ ] Flaky tests? (intermittent failures)
- [ ] Tests with hardcoded waits (cy.wait(5000) = bad)
- [ ] Tests without assertions (pointless tests)
- [ ] Over-mocking (mocking everything defeats the purpose)
- [ ] Under-mocking (calling real APIs in unit tests = integration test)
- [ ] Duplicate test cases (same thing tested multiple ways)
- [ ] Missing edge cases (null, empty, error scenarios)
- [ ] Test names unclear (should describe what's being tested)

**Test Quality Issues**:
- [ ] AAA pattern followed? (Arrange, Act, Assert)
- [ ] One assertion per test? (or logically grouped assertions)
- [ ] Tests independent? (can run in any order)
- [ ] Tests deterministic? (no random values, no Date.now())
- [ ] Proper cleanup (afterEach hooks for state reset)

### 3.2 Backend Tests (pytest)

**Static Analysis**:
```powershell
cd backend

# Test coverage with branch coverage
pytest --cov=src --cov-report=json --cov-report=html --cov-branch > ../analysis/pytest-coverage.txt

# Test duration analysis (slow tests)
pytest --durations=20 --durations-min=1.0 > ../analysis/slow-tests.txt

# Test collection (find uncollected test files)
pytest --collect-only -q > ../analysis/pytest-collection.txt
```

**Manual Review Checklist**:
- [ ] Test coverage >80%?
- [ ] Async tests properly marked (@pytest.mark.asyncio)?
- [ ] Fixtures reused (not duplicated across files)?
- [ ] Fixtures scope correct (function vs. module vs. session)?
- [ ] Mocking external services (SoundTouch API, RadioBrowser)?
- [ ] Database transactions rolled back (no test pollution)?
- [ ] Proper exception testing (pytest.raises)?
- [ ] Parametrize used for similar test cases?
- [ ] Test docstrings explain intent?

**Test Smells**:
- [ ] Tests longer than code being tested
- [ ] Tests with complex setup (extract to fixtures)
- [ ] Tests skipped without reason (@pytest.mark.skip without reason)
- [ ] Tests marked as xfail (expected to fail = technical debt)
- [ ] Slow tests (>1s for unit test = probably integration test)

### 3.3 Deliverable: Test Analysis Report

**Format** (max 2 pages):
```markdown
# Test Suite Analysis Report

## Coverage Summary
- Frontend Unit Tests: [%]
- Backend Unit Tests: [%]
- E2E Tests (Cypress): [scenarios covered]
- Total Coverage: [%]

## Test Quality Issues
### Critical
[Issues that make tests unreliable]

### High Priority
[Tests missing for critical paths]

## Test Cleanup Tasks
- Remove: [list obsolete tests]
- Refactor: [list tests needing rewrite]
- Add: [list missing test scenarios]

## Performance
- Slowest tests: [list with duration]
- Flaky tests: [list with failure rate]
```

---

## 📚 PHASE 4: DOCUMENTATION CLEANUP (45 minutes)

### 4.1 Documentation Inventory

**Scan all docs**:
```powershell
Get-ChildItem -Path docs,README.md,CONTRIBUTING.md,backend/README.md,frontend/README.md -Recurse -Include *.md | 
  Select-Object FullName, Length, LastWriteTime |
  Export-Csv -Path analysis/docs-inventory.csv
```

**Categorize each document**:

| Document | Category | Status | Action |
|----------|----------|--------|--------|
| README.md | Essential | Current | **CONSOLIDATE** (remove setup duplication) |
| docs/ITERATION_2.5.1_COMPLETE.md | Archive | Completed | **DELETE** (iteration done) |
| docs/MIGRATION_PROMPT.md | Archive | Obsolete | **DELETE** (migration done) |
| backend/bose_api/README.md | Reference | Current | **KEEP** (still needed) |
| docs/TESTING_REQUIREMENTS.md | Process | Current | **CONSOLIDATE** into CONTRIBUTING.md |
| docs/SoundTouchBridge_Projektplan.md | Planning | Obsolete | **DELETE** (historical, not actionable) |

**Categories**:
- **Essential**: README, CONTRIBUTING, API docs (KEEP, consolidate if needed)
- **Reference**: API schemas, architecture diagrams (KEEP if current, DELETE if obsolete)
- **Process**: Testing guides, development workflows (CONSOLIDATE into main docs)
- **Archive**: Iteration logs, migration notes, meeting notes (**DELETE ALL - NO ARCHIVE**)
- **Redundant**: Duplicate information (MERGE into canonical source)

### 4.2 Documentation Quality Criteria

**Each document MUST**:
- ✅ Be <10 minutes reading time (~2000 words max)
- ✅ Have clear purpose (stated in first paragraph)
- ✅ Be current (last update <3 months, or mark as outdated)
- ✅ Have unique information (no duplicates)
- ✅ Use concise language (no fluff, no repetition)
- ✅ Include code examples ONLY where essential (not for illustration)
- ✅ Have actionable content (if it doesn't guide a decision, delete it)

**PROHIBITED**:
- ❌ "Background" or "History" sections (nobody cares, delete)
- ❌ Long code examples (link to real code instead)
- ❌ Verbose explanations ("as we discussed earlier", "it's important to note")
- ❌ Redundant information (if it's in code comments, don't repeat in docs)
- ❌ Future plans (use GitHub Issues instead)
- ❌ Apologetic language ("this might not be perfect but...")

### 4.3 Documentation Cleanup Actions

**For each document, decide**:

1. **DELETE** (no questions asked):
   - Iteration logs (ITERATION_*.md)
   - Migration guides (MIGRATION_*.md)
   - Meeting notes
   - Old architecture docs (if superseded)
   - Draft documents
   - Test coverage reports (data is in htmlcov/)

2. **CONSOLIDATE** (merge into canonical source):
   - Multiple README files → One main README
   - Scattered testing docs → CONTRIBUTING.md
   - Deployment guides → DEPLOYMENT.md (one file)
   - Multiple API docs → backend/API.md

3. **REWRITE** (reduce to essentials):
   - Remove verbose intros
   - Keep only actionable content
   - Replace long examples with links to code
   - Use bullet points, not paragraphs
   - Add table of contents if >1000 words

4. **KEEP AS-IS** (rare):
   - backend/bose_api/README.md (concise reference)
   - LICENSE, NOTICE (legal requirement)

### 4.4 Documentation Structure (Target State)

```
/
├── README.md                    # Project overview, quick start (5 min read)
├── CONTRIBUTING.md              # Dev setup, testing, git workflow (8 min read)
├── DEPLOYMENT.md                # Production deployment (5 min read)
├── LICENSE                      # Keep as-is
├── NOTICE                       # Keep as-is
│
backend/
├── README.md                    # Backend-specific setup (3 min read)
├── API.md                       # API reference (8 min read)
└── bose_api/
    └── README.md                # Bose API docs (keep as-is)

frontend/
└── README.md                    # Frontend-specific setup (3 min read)

docs/
├── ARCHITECTURE.md              # System design (10 min read)
└── TROUBLESHOOTING.md           # Common issues (5 min read)

# EVERYTHING ELSE: DELETE!
```

---

## Phase 4.4: Scripts & Config Audit - "Assume Idiots Worked Here"

**⚠️ CRITICAL MINDSET: Question EVERYTHING. The previous developers were probably idiots who copy-pasted without understanding.**

### 4.4.1 Executable Scripts Audit

**Find all scripts**:
```powershell
Get-ChildItem -Path scripts/,deployment/,. -Include *.ps1,*.sh,*.py -Recurse | 
  Select-Object Name, Directory, Length, LastWriteTime |
  Export-Csv -Path analysis/scripts-inventory.csv
```

**For EACH script, answer**:
1. **What does it do?** (read the code, not just the header comment)
2. **Does it still work?** (run it, don't assume)
3. **Is it redundant?** (does another script/npm command do the same?)
4. **Is it outdated?** (references old paths, deleted files, wrong ports?)
5. **Should it even exist?** (or is this workflow obsolete?)

**Validation Checklist per Script**:
- [ ] Header comment matches actual functionality
- [ ] All referenced paths exist
- [ ] All referenced commands/tools are installed
- [ ] Error handling present (not just `$ErrorActionPreference = "Stop"`)
- [ ] Actually tested (run it, don't guess)
- [ ] Not duplicate of npm script or other script
- [ ] Still relevant to current workflow

**Common Script Smells**:
- ❌ References to deleted directories (`frontend-archive/`, `prototypes/`)
- ❌ Hardcoded ports that don't match current config
- ❌ Comments like "TODO: Update this" (it was never updated)
- ❌ Try-catch blocks that silently fail
- ❌ Functions that are never called
- ❌ Copy-paste from Stack Overflow without adaptation
- ❌ "Working around a bug in X" (bug probably fixed, workaround now causes bugs)

**Script Cleanup Actions**:

| Script | Status | Action | Reason |
|--------|--------|--------|--------|
| `scripts/run-all-tests.ps1` | ✅ Valid | **KEEP** | Runs unit + e2e, works |
| `scripts/run-real-tests.ps1` | ✅ Valid | **KEEP** | Specifically for real hardware |
| `scripts/old-deployment.ps1` | ❌ Broken | **DELETE** | References deleted `docker-compose-old.yml` |
| `deployment/deploy-local.ps1` | ⚠️ Redundant | **CONSOLIDATE** | Merge into `deploy-to-server.ps1` |

### 4.4.2 Configuration Files Audit - "Do We Really Need This?"

**Inventory ALL config files**:
```powershell
Get-ChildItem -Path . -Include *.json,*.yaml,*.yml,*.toml,*.ini,*.config.js,*.config.ts,.env*,.gitignore -Recurse -Depth 3 |
  Select-Object Name, Directory |
  Sort-Object Directory, Name
```

**For EACH config file, validate**:

#### **package.json / pyproject.toml - Dependencies**

**Questions**:
- ❓ Is this dependency actually used? (run `unimported` or `vulture`)
- ❓ Why this specific version? (can we upgrade? is pin necessary?)
- ❓ Do we need the entire library? (using lodash for 1 function?)
- ❓ Is there a lighter alternative? (moment.js vs. date-fns)
- ❓ Is this a dev dependency in production section? (mixing test libs with runtime libs)

**Example Audit**:
```json
// package.json - BEFORE (idiot mode)
{
  "dependencies": {
    "lodash": "^4.17.21",          // ❌ Used only for _.debounce - 24KB for 1 function!
    "moment": "^2.29.4",            // ❌ Not used anywhere (leftover from prototype)
    "react-router-dom": "^6.20.0", // ✅ Actually used
    "axios": "^1.6.0"              // ⚠️ Also have fetch - pick ONE
  },
  "devDependencies": {
    "vitest": "^1.0.0",            // ✅ Test runner
    "cypress": "^13.0.0",          // ⚠️ Do we need BOTH vitest AND cypress? (yes, different purposes)
    "react": "^18.2.0"             // ❌ Should be in dependencies, not devDependencies!
  }
}

// package.json - AFTER (professional)
{
  "dependencies": {
    "react": "^18.2.0",            // ✅ Moved from devDependencies
    "react-router-dom": "^6.20.0", // ✅ Keep
    // Removed: lodash (replaced with custom debounce)
    // Removed: moment (not used)
    // Removed: axios (use fetch API)
  },
  "devDependencies": {
    "vitest": "^1.0.0",            // ✅ Unit tests
    "cypress": "^13.0.0"           // ✅ E2E tests (different purpose than vitest)
  }
}
```

#### **Test Configuration Files**

**Files to audit**:
- `pytest.ini` - Is coverage threshold realistic? Are markers used?
- `vitest.config.js` - Do we need setup files? Are paths correct?
- `cypress.config.js` - Are viewport sizes current? Is baseUrl correct?
- `.coveragerc` / `coverage.json` - Duplicate config with pytest.ini?

**Critical Checks**:
- [ ] All paths in config exist
- [ ] No duplicate configs (e.g., coverage settings in 3 different files)
- [ ] Timeout values are realistic (not 1ms, not 5 minutes)
- [ ] Mock/stub paths point to existing files
- [ ] Excluded paths still make sense (excluding important code?)

**Example - pytest.ini**:
```ini
# BEFORE (copy-paste from tutorial)
[pytest]
testpaths = tests  # ✅ Good
asyncio_mode = auto  # ✅ Good
addopts = -v --strict-markers --cov=src --cov-fail-under=80  # ❌ BAD! Coverage should be optional

# AFTER (professional)
[pytest]
testpaths = tests
asyncio_mode = auto
addopts = -m "not real_devices"  # ✅ Exclude real hardware tests by default
# Coverage: Run explicitly with `pytest --cov=src --cov-fail-under=80`
```

#### **Build Configuration (vite.config.js, etc.)**

**Questions**:
- ❓ Are all plugins actually needed?
- ❓ Are build paths correct?
- ❓ Is output directory used anywhere?
- ❓ Are optimizations cargo-cult (copied without understanding)?

**Red Flags**:
- ❌ Comments like "not sure if needed but doesn't hurt" (DELETE IT THEN!)
- ❌ Experimental features enabled "just in case"
- ❌ Output to multiple directories (pick ONE)
- ❌ Sourcemaps disabled "for performance" (enable in dev, disable in prod properly)

#### **.env / .env.example**

**Validate**:
- [ ] All variables in `.env.example` are documented (what they do, valid values)
- [ ] No secrets in `.env.example` (only placeholders)
- [ ] All variables in `.env.example` are actually read by code
- [ ] No variables read by code but missing from `.env.example`

**Example**:
```bash
# .env.example - BEFORE (idiot mode)
API_URL=http://localhost:8000  # ❌ Not used anywhere in code
DEBUG=true                     # ❌ Ambiguous (what does this enable?)
SECRET_KEY=changeme            # ⚠️ Better: SECRET_KEY=your-secret-key-here

# .env.example - AFTER (professional)
# Backend API URL (default: http://localhost:7778)
CT_API_URL=http://localhost:7778

# Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
CT_LOG_LEVEL=INFO

# Discovery timeout in seconds (default: 10)
CT_DISCOVERY_TIMEOUT=10
```

### 4.4.3 Git Configuration Audit

**Files to check**:
- `.gitignore` - Is it ignoring what it should? Are patterns too broad?
- `.gitattributes` - Is LF/CRLF handling correct?
- Pre-commit hooks - Do they actually run? Are they fast enough?

**Gitignore Validation**:
```bash
# Find files that are ignored but shouldn't be:
git ls-files --others --ignored --exclude-standard

# Find files tracked that should be ignored:
git ls-files | grep -E "node_modules|__pycache__|\.pyc$|\.env$"
```

**Pre-commit Hook Validation**:
- [ ] Runs in <60 seconds (or developers will use `--no-verify`)
- [ ] Doesn't run **real device tests** (only mock/unit tests)
- [ ] Fails fast (don't run E2E if linting fails)
- [ ] Clear error messages (what failed, how to fix)

### 4.4.4 Docker/Deployment Config Audit

**Files**:
- `Dockerfile` (frontend + backend)
- `docker-compose.yml`
- Deployment scripts (`deploy-to-server.ps1`)

**Critical Questions**:
- ❓ Are base images pinned to specific versions? (not `python:latest`)
- ❓ Are multi-stage builds optimized? (minimal final image size)
- ❓ Are secrets handled correctly? (not hardcoded in Dockerfile)
- ❓ Are ports documented and consistent? (code vs. Docker vs. scripts)

**Example - Dockerfile**:
```dockerfile
# BEFORE (idiot mode)
FROM python:latest  # ❌ Unpinned version
RUN pip install -r requirements.txt  # ❌ No caching, slow rebuilds
COPY . .  # ❌ Copies everything (including .git, node_modules)

# AFTER (professional)
FROM python:3.13-slim  # ✅ Pinned version
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt  # ✅ Cache layer
COPY backend/src ./src  # ✅ Only production code
```

### 4.4.5 Deliverable: Scripts & Config Cleanup Plan

**Format**:
```markdown
# Scripts & Config Cleanup Plan

## Scripts to DELETE
- [ ] `scripts/old-deployment.ps1` - References deleted docker-compose-old.yml
- [ ] `deployment/export-image-old.ps1` - Duplicate of export-image.ps1
- [ ] `frontend/build-debug.ps1` - Never used, vite has debug mode built-in

Total: [N] scripts deleted

## Scripts to FIX
| Script | Issue | Fix |
|--------|-------|-----|
| `run-all-tests.ps1` | Includes real tests | Add `-m "not real_devices"` to pytest call |
| `deploy-local.ps1` | Hardcoded port 8000 | Use config from .env |

## Config Files to CONSOLIDATE
- Merge `.coveragerc` into `pytest.ini` (duplicate coverage config)
- Remove `vitest.setup.old.js` (replaced by vitest.config.js)

## Dependencies to REMOVE
### Frontend (package.json)
- `lodash` (24KB) → Replace with custom debounce (0.5KB)
- `moment` → Not used anywhere, DELETE

### Backend (requirements.txt)
- `requests` → Already have httpx (async), use that
- `pyyaml` → Only used in 1 test, mock it instead

## Config Issues to FIX
- `pytest.ini`: Move coverage to optional (not in addopts)
- `.env.example`: Add missing CT_MANUAL_DEVICE_IPS variable
- `vite.config.js`: Remove unused plugin `vite-plugin-pwa`
```

---

## Phase 4.5: Deliverable: Documentation Cleanup Plan

**Format**:
```markdown
# Documentation Cleanup Plan

## Files to DELETE (no archive)
- [ ] docs/ITERATION_2.5.1_COMPLETE.md
- [ ] docs/MIGRATION_PROMPT.md
- [ ] docs/MIGRATION_TO_CLEAN_TEST_ARCHITECTURE.md
- [ ] docs/SoundTouchBridge_Projektplan.md
- [ ] docs/archive/* (entire directory)
[... full list ...]

Total: [N] files, [MB] disk space

## Files to CONSOLIDATE

### README.md ← backend/README.md, frontend/README.md
**Action**: Merge backend/frontend setup into main README under "Development" section
**Before**: 3 files, 15 min total read time
**After**: 1 file, 5 min read time

### CONTRIBUTING.md ← docs/TESTING_REQUIREMENTS.md, docs/PRE-COMMIT-HOOK.md
**Action**: Merge testing and git workflow into CONTRIBUTING
**Before**: 3 files, 20 min total read time
**After**: 1 file, 8 min read time

[... more consolidations ...]

## Files to REWRITE (>10 min read time)
- [ ] docs/ARCHITECTURE.md (currently 25 min) → target 10 min
  - Remove: History, Background (3 pages)
  - Condense: Code examples → links to actual code
  - Keep: Architecture diagram, layer descriptions, design decisions

[... more rewrites ...]

## Final Documentation Size
- Before: [N] files, [total words], [estimated read time]
- After: [M] files (<10), [total words], [<60 min total]
- Reduction: [%]
```

---

## 🛠️ PHASE 5: CLEANUP EXECUTION (120 minutes)

### 5.1 Frontend Cleanup Tasks

**Priority Order**:
1. **Critical issues** (blocking production)
2. **Security issues** (npm audit findings)
3. **Architecture violations** (wrong dependencies, state management mess)
4. **Code smells** (magic numbers, duplication)
5. **Dependencies** (remove unused, update outdated)
6. **Dead code** (remove unused files/functions)
7. **Formatting** (run Prettier)

**For each issue**:
```markdown
### Issue: [Title from analysis report]
- **Fix**: [Exact code change]
- **Test**: [How to verify fix works]
- **Commit**: `refactor(frontend): [description]`
```

**Execute**:
```powershell
# Fix linting issues
npm run lint -- --fix

# Format code
npx prettier --write "src/**/*.{js,jsx,css}"

# Remove unused dependencies
npm uninstall [list from analysis]

# Update dependencies (safe updates only)
npm update --save

# Re-run tests
npm run test
npm run test:e2e

# Verify no regressions
npm run build
```

### 5.2 Backend Cleanup Tasks

**Priority Order**:
1. **Security issues** (Bandit, Safety findings)
2. **Critical bugs** (type errors, logic errors)
3. **Architecture violations** (layer mixing, wrong dependencies)
4. **Code smells** (god classes, long functions)
5. **Dependencies** (remove unused, update safe)
6. **Dead code** (remove unused modules)
7. **Formatting** (run Black, isort)

**Execute**:
```powershell
# Fix auto-fixable issues
ruff check src/ tests/ --fix

# Format code
black src/ tests/
isort src/ tests/

# Remove unused dependencies
# (manual: edit pyproject.toml, then:)
pip install -e ".[dev]"

# Re-run tests
pytest --cov=src --cov-fail-under=80

# Type check
mypy src/ --strict

# Security scan
bandit -r src/ -ll
```

### 5.3 Test Cleanup Tasks

**Frontend**:
```powershell
# Remove obsolete test files
Remove-Item [list from analysis]

# Update test dependencies
npm update --save-dev [test libraries]

# Re-run with coverage
npm run test:coverage

# Verify >80% coverage
```

**Backend**:
```powershell
# Remove obsolete test files
Remove-Item [list from analysis]

# Refactor slow tests (mock external calls)
# Refactor flaky tests (remove hardcoded waits)

# Re-run with strict coverage
pytest --cov=src --cov-fail-under=80 --cov-branch

# Check for test leaks
pytest -x --lf
```

### 5.4 Documentation Cleanup Tasks

**Execute**:
```powershell
# DELETE files (NO ARCHIVE!)
Remove-Item docs/ITERATION_*.md
Remove-Item docs/MIGRATION_*.md
Remove-Item -Recurse docs/archive/

# CONSOLIDATE files
# (manual editing per plan)

# REWRITE files
# (manual editing per plan)

# Verify all links work
# (use markdown-link-check or similar)

# Final review: each doc <10 min read
```

---

## ✅ PHASE 6: QUALITY GATES & VALIDATION (30 minutes)

### 6.1 Code Quality Gates

**All must pass**:
```powershell
# Frontend
cd frontend
npm run lint          # 0 errors
npm run test          # 100% pass, >80% coverage
npm run build         # successful build

# Backend
cd backend
ruff check src/ tests/               # 0 errors
black --check src/ tests/            # no formatting issues
mypy src/ --strict                   # 0 type errors
pytest --cov=src --cov-fail-under=80 # >80% coverage
bandit -r src/ -ll                   # 0 high/medium security issues
```

### 6.2 Documentation Quality Gates

**All must pass**:
- [ ] Total docs <10 files
- [ ] Each doc <10 min read time
- [ ] No iteration/migration logs remaining
- [ ] No duplicate information
- [ ] All code examples link to real code (or removed)
- [ ] All links work (no 404s)
- [ ] TOC present for docs >1000 words

### 6.3 Functional Validation

**E2E tests must pass**:
```powershell
# Cypress
cd frontend
npm run test:e2e

# Backend E2E
cd backend
pytest tests/e2e/
```

### 6.4 Git Cleanliness

**Verify**:
```powershell
# No uncommitted changes (except deliberate)
git status

# No ignored files that should be tracked
git ls-files --others --exclude-standard

# No large files accidentally committed
git ls-files | ForEach-Object { Get-Item $_ } | Where-Object { $_.Length -gt 1MB }
```

---

## 📊 PHASE 7: FINAL REPORT (30 minutes)

### 7.1 Cleanup Summary

**Format**:
```markdown
# CloudTouch Codebase Cleanup - Final Report

**Date**: [YYYY-MM-DD]
**Duration**: [total hours]
**Status**: ✅ COMPLETE

## Metrics

### Code
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Frontend LoC | [N] | [M] | -[X]% |
| Backend LoC | [N] | [M] | -[X]% |
| Cyclomatic Complexity (avg) | [N] | [M] | -[X]% |
| Test Coverage | [N]% | [M]% | +[X]% |
| ESLint Errors | [N] | 0 | -100% |
| MyPy Errors | [N] | 0 | -100% |
| Security Issues | [N] | 0 | -100% |

### Dependencies
| | Before | After | Removed |
|-|--------|-------|---------|
| Frontend | [N] | [M] | [X] |
| Backend | [N] | [M] | [X] |

### Documentation
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total Files | [N] | [M] | -[X]% |
| Total Words | [N] | [M] | -[X]% |
| Read Time | [N] min | [M] min | -[X]% |

## Changes Summary

### Frontend
- Fixed [N] critical issues
- Removed [N] unused dependencies
- Deleted [N] dead code files
- Refactored [N] complex components

### Backend
- Fixed [N] architecture violations
- Removed [N] workarounds
- Consolidated [N] duplicate functions
- Updated [N] dependencies

### Tests
- Removed [N] obsolete tests
- Fixed [N] flaky tests
- Added [N] missing test scenarios
- Coverage: [X]% → [Y]%

### Documentation
- Deleted [N] files ([MB] saved)
- Consolidated [N] files
- Rewrote [N] files (reduced by [X]%)

## Technical Debt Eliminated

### Critical (Blockers)
1. [Description] - Fixed in [commit hash]
2. [...]

### High Priority
1. [Description] - Fixed in [commit hash]
2. [...]

## Remaining Known Issues

### Technical Debt (Accepted)
1. [Description] - Reason for keeping: [justification]

### Future Improvements (Backlog)
1. [Description] - Estimated effort: [hours]

## Commits
- Total commits: [N]
- Commit message format: Conventional Commits (feat, fix, refactor, docs, test)
- Branch: `cleanup/[YYYY-MM-DD]`

## Quality Gates Status
- [x] All linters pass
- [x] All tests pass (>80% coverage)
- [x] No security vulnerabilities
- [x] Documentation <10 files, each <10 min read
- [x] E2E tests pass
- [x] Build successful
```

### 7.2 Git Commit Strategy

**Branch**:
```powershell
git checkout -b cleanup/2026-02-03
```

**Commits (atomic, in order)**:
```powershell
# Frontend
git commit -m "refactor(frontend): remove unused dependencies"
git commit -m "fix(frontend): eliminate setTimeout race condition workaround in DeviceList"
git commit -m "refactor(frontend): extract duplicate API calls to centralized service"
git commit -m "style(frontend): apply Prettier formatting"
git commit -m "test(frontend): remove obsolete test files"

# Backend
git commit -m "refactor(backend): fix layer mixing in device repository"
git commit -m "fix(backend): replace hardcoded timeouts with config values"
git commit -m "refactor(backend): consolidate duplicate error handling"
git commit -m "style(backend): apply Black and isort formatting"
git commit -m "test(backend): fix flaky SSDP discovery tests"

# Documentation
git commit -m "docs: delete completed iteration logs and migration guides"
git commit -m "docs: consolidate README files into main README"
git commit -m "docs: rewrite ARCHITECTURE.md to <10 min read time"

# Final
git commit -m "chore: update dependencies to latest secure versions"
git commit -m "ci: add static analysis to pre-commit hook"
```

**Push & Review**:
```powershell
git push origin cleanup/2026-02-03

# USER REVIEWS CHANGES
# USER RUNS MANUAL TESTS
# USER APPROVES

# Then on USER instruction:
git checkout main
git merge --no-ff cleanup/2026-02-03
git push origin main
```

---

## 🚨 EXCEPTION HANDLING

### What if Analysis Reveals MAJOR Architectural Problems?

**Scenario**: Layer violations everywhere, state management chaos, test coverage <50%

**Action**:
1. **STOP cleanup execution**
2. **Document findings** in `CRITICAL_ISSUES.md`
3. **Propose refactoring plan** with estimated effort
4. **Get user approval** before proceeding
5. **Execute in phases** (not one big cleanup)

**Example**:
```markdown
# CRITICAL: Frontend State Management Chaos

## Problem
- Redux used in 3 components
- Context used in 5 components
- Local useState in 15 components
- Prop drilling 5 levels deep in 2 places

## Impact
- Hard to maintain
- Unclear data flow
- Duplicate state
- Race conditions

## Proposed Solution
**Option 1**: Standardize on Redux (2 days effort)
**Option 2**: Standardize on Context (1 day effort)
**Option 3**: Hybrid (Redux for global, Context for features) (1.5 days)

## Recommendation
Option 2 (Context) - simplest, fits project size

## Next Steps
1. USER APPROVAL REQUIRED
2. Create separate refactoring branch
3. Migrate incrementally (one feature at a time)
4. Update tests after each migration
5. Merge when all tests pass
```

### What if Tests Start Failing During Cleanup?

**Root Cause Analysis**:
1. Did cleanup introduce a bug? → **REVERT**, fix properly
2. Was test relying on implementation detail? → **FIX TEST** (test behavior, not implementation)
3. Was test flaky to begin with? → **FIX TEST** (remove race conditions)

**Never**:
- ❌ Skip failing tests
- ❌ Mark as xfail
- ❌ Lower coverage threshold

**Always**:
- ✅ Understand why test failed
- ✅ Fix root cause
- ✅ Add regression test if needed

### What if Dependencies Can't Be Updated?

**Scenario**: Dependency X has breaking changes, major refactor needed

**Action**:
1. **Document** in `DEPENDENCIES.md`:
   ```markdown
   ## Pinned Dependencies
   
   ### httpx==0.24.1 (pinned, not latest 0.27.0)
   **Reason**: Version 0.25+ changed async API, requires refactoring all API calls
   **Impact**: Missing performance improvements, security patches
   **Plan**: Upgrade in Q2 2026 (dedicated refactoring sprint)
   **Tracking**: Issue #123
   ```

2. **Add to backlog**, don't block cleanup

### What if User Wants to Keep "Archive" Docs?

**Push back gently**:
```
"Archive documents create maintenance burden and confusion. 
Historical context belongs in git history, not docs.

If specific information is valuable:
1. Extract essential facts
2. Add to relevant current doc
3. Delete archive

What specific information from [doc] do you need to preserve?"
```

**If user insists**:
- Create `docs/archive/` folder
- Add `README.md` with warning: "Historical docs, may be outdated"
- Never link to archive from main docs

---

## 🎯 SUCCESS CRITERIA

**Cleanup is COMPLETE when**:

### Code
- [x] All static analysis tools report 0 errors
- [x] Test coverage ≥80% (both frontend and backend)
- [x] No workarounds or TODO comments (or tracked in issues)
- [x] Dependencies up-to-date (or explicitly pinned with reason)
- [x] No dead code (verified with unimported/vulture)
- [x] Consistent code style (Prettier/Black applied)

### Tests
- [x] All tests pass
- [x] No flaky tests (5 consecutive runs, all pass)
- [x] No slow unit tests (>1s = integration test, move to separate suite)
- [x] E2E tests cover critical user paths

### Documentation
- [x] ≤10 documentation files total
- [x] Each doc ≤10 min read time (~2000 words)
- [x] No iteration/migration/archive docs
- [x] No duplicate information
- [x] All links work

### Functional
- [x] Application runs locally (npm run dev, uvicorn)
- [x] E2E tests pass
- [x] No errors in browser console
- [x] No errors in backend logs

### Git
- [x] All changes committed (atomic commits)
- [x] Conventional commit messages
- [x] Branch ready for merge
- [x] No merge conflicts with main

---

## 🏗️ CLEANUP PATTERNS & BEST PRACTICES

### Pattern 1: Strangler Fig Pattern (for large refactorings)

**When to use**: Replacing large, complex modules without breaking everything

**Process**:
1. **Build new implementation** alongside old (both exist in parallel)
2. **Route new usage** to new code (via feature flag or config)
3. **Gradually migrate** existing code paths to new implementation
4. **Monitor** for issues (logging, metrics)
5. **Delete old code** when nothing uses it anymore

**Example**:
```python
# OLD: Tight coupling, hard to test
class DeviceDiscovery:
    def find_devices(self):
        # Complex SSDP logic mixed with HTTP calls
        pass

# NEW: Clean separation, testable
class SSDPDiscovery(DeviceDiscovery):
    def find_devices(self):
        # Pure SSDP logic
        pass

# MIGRATION: Use feature flag
def get_discovery_service():
    if config.use_new_discovery:
        return SSDPDiscovery()
    else:
        return LegacyDeviceDiscovery()

# USAGE: Gradually migrate
discovery = get_discovery_service()
devices = discovery.find_devices()
```

**Benefits**:
- ✅ No "big bang" rewrites
- ✅ Can revert quickly if issues
- ✅ Continuous integration (tests always pass)
- ✅ Low risk

### Pattern 2: Adapter Pattern (for external dependencies)

**When to use**: Wrapping third-party libraries, external APIs, or volatile code

**Process**:
1. **Define interface** (what operations do you need?)
2. **Implement adapter** (wraps external library)
3. **Replace direct usage** with adapter
4. **Mock adapter** in tests (not the external library)

**Example**:
```python
# BAD: Direct dependency on httpx everywhere
async def get_device_info(ip: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://{ip}:8090/info")
        return response.text

# GOOD: Adapter pattern
class HTTPClient(ABC):
    @abstractmethod
    async def get(self, url: str) -> str:
        pass

class HTTPXAdapter(HTTPClient):
    async def get(self, url: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.text

# USAGE: Dependency injection
class DeviceService:
    def __init__(self, http: HTTPClient):
        self.http = http
    
    async def get_info(self, ip: str):
        xml = await self.http.get(f"http://{ip}:8090/info")
        return parse_xml(xml)

# TESTING: Easy mocking
def test_device_service():
    mock_http = Mock(HTTPClient)
    mock_http.get.return_value = "<info>...</info>"
    service = DeviceService(mock_http)
    info = service.get_info("192.168.1.100")
    # Test passes without real HTTP calls!
```

**Benefits**:
- ✅ Easy to swap implementations (e.g., httpx → aiohttp)
- ✅ Testable without external dependencies
- ✅ Isolates breaking changes in libraries

### Pattern 3: Feature Flags (for risky changes)

**When to use**: Deploying risky changes, A/B testing, gradual rollout

**Process**:
1. **Add config flag** (env var or config file)
2. **Implement new code** behind flag
3. **Deploy with flag OFF** (default to safe behavior)
4. **Enable flag** gradually (test in dev → staging → prod)
5. **Remove flag** once stable (make new code default)

**Example**:
```python
# Config
USE_NEW_PRESET_API = os.getenv("CT_USE_NEW_PRESET_API", "false").lower() == "true"

# Code
async def save_preset(device_id: str, preset: int, station: str):
    if USE_NEW_PRESET_API:
        # New implementation (risky, but better)
        return await new_preset_service.save(device_id, preset, station)
    else:
        # Old implementation (stable, proven)
        return await legacy_preset_save(device_id, preset, station)
```

**Benefits**:
- ✅ Can deploy without risk
- ✅ Can revert instantly (flip flag)
- ✅ Can test in production safely

### Pattern 4: SOLID Principles Reminder

**S - Single Responsibility**
- One class = one reason to change
- ❌ BAD: `DeviceManager` does discovery + API calls + DB + UI updates
- ✅ GOOD: `DeviceDiscovery`, `DeviceRepository`, `DeviceAPIClient` (separate)

**O - Open/Closed**
- Open for extension, closed for modification
- ❌ BAD: `if provider == "radiobrowser": ... elif provider == "tunein": ...` (modify class for each provider)
- ✅ GOOD: `RadioProvider` interface, `RadioBrowserProvider`, `TuneInProvider` (extend with new classes)

**L - Liskov Substitution**
- Subtypes must be substitutable for base types
- ❌ BAD: `Square` inherits `Rectangle` but breaks `set_width()/set_height()` invariants
- ✅ GOOD: Composition over inheritance (`Square` has-a `dimensions`, not is-a `Rectangle`)

**I - Interface Segregation**
- Many small interfaces > one fat interface
- ❌ BAD: `IDevice` with 50 methods (most devices implement only 10)
- ✅ GOOD: `IPlayback`, `IVolume`, `IPresets` (devices implement only what they support)

**D - Dependency Inversion**
- Depend on abstractions, not concretions
- ❌ BAD: `DeviceService` creates `HTTPXClient()` directly
- ✅ GOOD: `DeviceService(http: HTTPClient)` - depends on interface, not implementation

### Pattern 5: Progressive Enhancement (UI)

**When to use**: Building user-facing features that should work everywhere

**Process**:
1. **Base functionality** works without JavaScript (HTML + CSS)
2. **Enhanced functionality** if JavaScript enabled (interactivity)
3. **Progressive features** if modern browser (animations, web workers)

**Example**:
```jsx
// LEVEL 1: Works without JavaScript (server-rendered HTML)
<form action="/api/devices/sync" method="POST">
  <button type="submit">Sync Devices</button>
</form>

// LEVEL 2: Enhanced with JavaScript (no page reload)
function DeviceSyncButton() {
  const handleSync = async () => {
    await fetch('/api/devices/sync', { method: 'POST' });
    alert('Synced!');
  };
  return <button onClick={handleSync}>Sync Devices</button>;
}

// LEVEL 3: Progressive (loading state, animations)
function DeviceSyncButton() {
  const [loading, setLoading] = useState(false);
  const handleSync = async () => {
    setLoading(true);
    await fetch('/api/devices/sync', { method: 'POST' });
    setLoading(false);
  };
  return (
    <motion.button 
      onClick={handleSync} 
      disabled={loading}
      whileHover={{ scale: 1.05 }}
    >
      {loading ? <Spinner /> : 'Sync Devices'}
    </motion.button>
  );
}
```

**Benefits**:
- ✅ Works for everyone (accessibility)
- ✅ Graceful degradation
- ✅ Better UX for modern browsers

### Pattern 6: The Boy Scout Rule

> "Leave the code better than you found it"

**Every cleanup should**:
- Fix the original problem
- Plus one small improvement nearby
- Example: Fix a bug → also improve variable naming in that function

**Cumulative effect**: Codebase gets cleaner over time

---

## 📝 FINAL CHECKLIST FOR AGENT

**Before starting**:
- [ ] Read AGENTS.md (project-specific rules)
- [ ] Read this prompt completely
- [ ] Understand TDD requirements (tests must pass always)
- [ ] Understand USER AUTHORITY (no experiments without approval)

**Phase 0 (Context)**:
- [ ] Analyze Cypress tests
- [ ] Create temporary context doc
- [ ] Get user approval on context understanding

**Phase 1-3 (Analysis)**:
- [ ] Run all static analysis tools
- [ ] Manual code review with checklists
- [ ] Document ALL findings (not just selected ones)
- [ ] Categorize by priority (Critical, High, Medium, Low)
- [ ] Estimate effort for each fix

**Phase 4 (Documentation)**:
- [ ] Inventory all docs with metadata
- [ ] Categorize each (Essential, Reference, Process, Archive, Redundant)
- [ ] Create DELETE list (user approval required!)
- [ ] Create CONSOLIDATE plan
- [ ] Create REWRITE list with word count targets

**Phase 5 (Execution)**:
- [ ] Fix in priority order (Critical → Low)
- [ ] ONE COMMIT PER LOGICAL CHANGE
- [ ] Run tests after EVERY change
- [ ] Never bypass pre-commit hooks
- [ ] Never commit broken code
- [ ] Document any exceptions/trade-offs

**Phase 6 (Validation)**:
- [ ] All quality gates pass
- [ ] Manual smoke test (app works)
- [ ] No regressions in E2E tests

**Phase 7 (Report)**:
- [ ] Create final report with metrics
- [ ] List all commits
- [ ] Document remaining known issues
- [ ] Get user approval for merge

**After merge**:
- [ ] Delete cleanup branch (after successful merge)
- [ ] Close related issues
- [ ] Update project status

---

## 🎯 CRITICAL SUCCESS CRITERIA - "Professional Workspace" Checklist

**When cleanup is complete, the workspace MUST feel like**:
✅ A project maintained by senior engineers who care about quality  
✅ A codebase you'd proudly show at a job interview  
✅ Documentation you can read in <30 minutes and understand everything  
✅ Scripts that work the first time, every time  
✅ Config files where every line has a clear purpose  
✅ Tests that run in <60 seconds and never flake  
✅ Zero "TODO" comments older than 1 week  
✅ Zero files with "old", "backup", "temp", "test" in the name  
✅ Zero copy-pasted code from Stack Overflow without attribution/understanding  
✅ Zero "this is a workaround for..." comments  

**Red Flags (if you see these, cleanup FAILED)**:
❌ "I think this script still works..."  
❌ "Not sure what this config does, but removing it breaks things..."  
❌ "The tests pass on my machine..."  
❌ "We keep this file just in case..."  
❌ "This workaround is temporary..." (from 6 months ago)  
❌ "I'll clean this up later..."  

---

## 🔗 RELATED DOCUMENTS

- `AGENTS.md` - General agent rules (TDD, Clean Code, etc.)
- `CONTRIBUTING.md` - Development workflow
- `backend/bose_api/README.md` - Bose API reference

---

**REMEMBER**: 
- **Assume idiots worked here** - Validate everything, trust nothing
- **Code quality > speed** - Better slow and correct than fast and broken
- **Tests must ALWAYS pass** - Green before commit, green after commit
- **Real tests NEVER in automation** - Only mock/unit tests in CI/pre-commit
- **User approval required** - For structural changes >20h effort
- **Document trade-offs** - If you keep a workaround, explain WHY
- **No experiments** - Cleanup is about removing complexity, not adding features

**START WITH PHASE 0 - CONTEXT ACQUISITION**
