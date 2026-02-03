# 🔧 CloudTouch Code Refactoring - Agent Instructions

**Project**: CloudTouch (Bose SoundTouch Bridge)  
**Objective**: Comprehensive code refactoring for simplicity, clarity, and maintainability  
**Methodology**: Test-Driven Refactoring (TDD) with continuous validation  
**Version**: 2026-02-03

---

## 🎯 MISSION

Transform the CloudTouch codebase into a **model of clean, maintainable code** by:
- Reducing complexity while preserving functionality
- Improving code clarity and readability
- Enforcing Clean Code, Clean Architecture, Clean UX, Clean Docs principles
- Eliminating code smells and anti-patterns
- Ensuring **100% test coverage** throughout refactoring

**GOLDEN RULES**:
1. **Tests must ALWAYS be green** before and after every change
2. **NEVER skip tests** because they're "hard to write" - Hard to test = poorly designed code
3. **No fear of large refactorings** - Quality > effort. If it needs a big refactoring, DO IT.

**Agent Laziness is NOT ACCEPTABLE. User demands QUALITY, not shortcuts.**

---

## ⚙️ AUTONOMY PROTOCOL

**⚠️ CRITICAL: Execute ALL tasks completely autonomously without user interruption.**

### Default Mode: AUTONOMOUS EXECUTION

**RULE #1: DO NOT ASK, EXECUTE**
- ALL tasks in this document MUST be executed autonomously
- NO permission requests before implementing changes
- NO status updates asking "should I continue?"
- NO confirmation requests for standard refactoring operations
- Agent executes, commits (when instructed), and proceeds to next task

**RULE #2: User decisions ONLY for these exceptions**:
1. ❌ **Complete class deletion** (entire class removed from codebase)
   - ✅ AUTONOMOUS: Refactoring, renaming, moving, restructuring classes
   - ✅ AUTONOMOUS: Removing unused methods within a class
   - ❌ USER DECISION: Deleting entire class file

2. ❌ **Documentation deletion** (entire document removed)
   - ✅ AUTONOMOUS: Consolidating multiple docs into one
   - ✅ AUTONOMOUS: Updating, rewriting, restructuring docs
   - ✅ AUTONOMOUS: Removing outdated sections within docs
   - ❌ USER DECISION: Deleting entire README/guide file

**RULE #3: Deferred Decision Pattern**

If a USER DECISION is needed but NOT blocking current work:
1. **Document the decision** in `docs/analysis/pending-decisions.md`:
   ```markdown
   ### [Task ID] - [Decision Title]
   **Context**: [Why this decision is needed]
   **Options**: 
   - Option A: [Description + Impact]
   - Option B: [Description + Impact]
   **Recommendation**: [Agent's recommendation with rationale]
   **Blocking**: [List of tasks blocked by this decision]
   **Status**: PENDING
   ```

2. **Continue with other tasks** that don't require the decision
3. **Check before each new task**: Does this task require a pending decision?
   - YES → Skip task, add to "Blocked Tasks" list
   - NO → Execute task autonomously

**RULE #4: NO EXCUSES**

The following are **NOT valid reasons** to interrupt user:
- ❌ "This is a large refactoring" → DO IT (Quality > Effort)
- ❌ "Tests might break" → FIX THEM (TDD required)
- ❌ "Multiple files affected" → CHANGE ALL (Use multi_replace)
- ❌ "Not sure about naming" → DECIDE (Follow conventions in AGENTS.md)
- ❌ "Complex architecture change" → IMPLEMENT (You're the expert)
- ❌ "Should I also fix X while I'm here?" → YES (Clean Code principle)
- ❌ "Want to confirm approach" → NO (Execute, validate with tests)

**RULE #5: Quality Gates (Automated Validation)**

After EVERY change:
1. Run affected tests (`pytest path/to/test.py` or `npm test -- file.test.jsx`)
2. If tests fail → Fix immediately (no user escalation)
3. If coverage drops → Add tests immediately
4. If linter fails → Fix immediately
5. Only escalate if:
   - Technical blocker (missing credentials, external service down)
   - Requires complete class deletion (see RULE #2)
   - Requires documentation deletion (see RULE #2)

**RULE #6: Commit Strategy (When Instructed)**

Per AGENTS.md, commits ONLY on explicit user instruction ("commit", "commit & push").
BUT within a session:
- ✅ Execute 10-20 tasks continuously
- ✅ Keep all tests green
- ✅ Build cohesive changeset
- ❌ Stop after each task asking "commit now?"

User will decide when to commit the accumulated changes.

**ENFORCEMENT**:

If agent interrupts user for non-exception reasons:
- ❌ **VIOLATION**: Agent stops work and asks "Should I refactor this function?"
- ✅ **CORRECT**: Agent refactors function, runs tests, proceeds to next task

**Autonomy Checklist (Before ANY user interaction)**:
- [ ] Is this a complete class deletion? (If NO → Don't ask)
- [ ] Is this a complete documentation deletion? (If NO → Don't ask)
- [ ] Is there a technical blocker I cannot resolve? (If NO → Don't ask)
- [ ] Can I defer this decision and continue other work? (If YES → Defer and continue)

**If all 4 answers allow autonomous execution → EXECUTE, DO NOT ASK.**

---

## 📚 MANDATORY READING BEFORE START

**You MUST read and internalize these documents first**:

1. **AGENTS.md** - Project-specific development rules, TDD requirements, commit guidelines
2. **backend/bose_api/README.md** - Bose SoundTouch API documentation and capability detection
3. **CONTRIBUTING.md** - Development workflow, testing requirements
4. **Current test suites** - Understand what the application does by reading tests

**Time allocation**: 45 minutes reading before any code analysis.

---

## 🧠 PHASE 0: DEEP CONTEXT ACQUISITION (90 minutes)

### 0.1 Build Mental Model of Application

**Objective**: Understand the ENTIRE codebase structure before touching any code.

#### Step 1: Read ALL Test Files First (45 minutes)

**Why tests first?**
- Tests describe expected behavior (the "what")
- Tests reveal business logic and use cases
- Tests show integration points and dependencies
- Tests highlight critical paths

**Read in this order**:

```powershell
# 1. E2E Tests (User perspective)
backend/tests/e2e/**/*.py
frontend/cypress/e2e/**/*.cy.js

# 2. Integration Tests (Component interaction)
backend/tests/integration/**/*.py
frontend/tests/integration/**/*.test.jsx

# 3. Unit Tests (Individual components)
backend/tests/unit/**/*.py
frontend/tests/unit/**/*.test.jsx
```

**For each test file, document**:
```markdown
### [Test File Name]
- **Purpose**: What is being tested?
- **Critical Paths**: Which scenarios are most important?
- **Dependencies**: What external systems are mocked/used?
- **Edge Cases**: What error scenarios are covered?
- **Gaps**: What scenarios are missing tests?
```

**Deliverable**: `analysis/test-inventory.md` (3-5 pages)

#### Step 2: Map the Architecture (30 minutes)

**Scan directory structure**:
```powershell
# Get complete file tree
Get-ChildItem -Path backend/src,frontend/src -Recurse -File | 
  Select-Object FullName, Length, LastWriteTime |
  Export-Csv analysis/file-inventory.csv

# Count lines of code per module
Get-ChildItem -Path backend/src,frontend/src -Recurse -Filter *.py,*.js,*.jsx |
  ForEach-Object { 
    [PSCustomObject]@{
      File = $_.FullName
      Lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
    }
  } | Export-Csv analysis/loc-per-file.csv
```

**Identify architecture layers**:
- Frontend: Components → Services → State → API Client
- Backend: API Routes → Use Cases → Domain → Adapters → Infrastructure

**Deliverable**: `analysis/architecture-map.md` with:
```markdown
# Architecture Map

## Frontend Layers
- **Components**: [list directories and purpose]
- **Services**: [list files and responsibilities]
- **State Management**: [Redux/Context/useState patterns found]
- **API Integration**: [how backend is called]

## Backend Layers
- **API Layer**: [FastAPI routes, endpoints]
- **Use Cases**: [business logic modules]
- **Domain Models**: [core entities]
- **Adapters**: [external system integrations]
- **Infrastructure**: [DB, config, logging]

## Cross-Cutting Concerns
- **Error Handling**: [patterns used]
- **Logging**: [where and how]
- **Configuration**: [env vars, config files]
- **Authentication**: [if any]

## Dependencies Flow
[Diagram showing which layers depend on which]
```

#### Step 3: Read Every Source File Line-by-Line (15 minutes per file)

**Critical: Do NOT skip this step!**

**For EACH source file, analyze**:

```markdown
### [Filename with path]

**Purpose**: [1 sentence - what does this file do?]

**Complexity Score**: [1-10, where 10 = incomprehensible]

**Key Functions/Classes**:
- `functionName()`: [purpose, complexity, issues]
- `ClassName`: [responsibility, dependencies, issues]

**Dependencies**:
- External: [libraries used]
- Internal: [other modules imported]

**Code Smells Detected**:
- [ ] Long functions (>50 lines)
- [ ] God classes (>300 lines, too many responsibilities)
- [ ] Deep nesting (>3 levels)
- [ ] Magic numbers/strings
- [ ] Commented-out code
- [ ] Copy-pasted code
- [ ] Missing error handling
- [ ] Poor naming
- [ ] Tight coupling

**Refactoring Opportunities**:
1. [Specific improvement with line numbers]
2. [...]

**Test Coverage**:
- Current: [%] (check htmlcov/)
- Missing scenarios: [list]

**Estimated Refactoring Time**: [minutes]
```

**Deliverable**: `analysis/file-by-file-review.md` (comprehensive, 20-50 pages)

---

## 🔍 PHASE 1: STATIC ANALYSIS & METRICS (30 minutes)

### 1.1 Run All Static Analysis Tools

**Frontend**:
```powershell
cd frontend

# ESLint (detect code issues)
npm run lint -- --format json --output-file ../analysis/eslint-report.json

# Prettier (formatting consistency)
npx prettier --check "src/**/*.{js,jsx,css}" > ../analysis/prettier-violations.txt

# Complexity analysis
npx es6-plato -r -d ../analysis/complexity-frontend src/

# Bundle size
npm run build
npx vite-bundle-visualizer dist/stats.json > ../analysis/bundle-analysis.txt

# Unused code
npx unimported > ../analysis/dead-code-frontend.txt

# Duplicate code detection
npx jscpd src/ --format json --output ../analysis/duplicate-code-frontend.json
```

**Backend**:
```powershell
cd backend

# Ruff (linting)
ruff check src/ --output-format json > ../analysis/ruff-report.json

# Black (formatting)
black --check src/ > ../analysis/black-violations.txt

# MyPy (type checking)
mypy src/ --strict --json-report ../analysis/mypy-report/

# Cyclomatic complexity
radon cc src/ -a -s -j > ../analysis/radon-complexity.json
radon mi src/ -s -j > ../analysis/radon-maintainability.json

# Dead code
vulture src/ > ../analysis/dead-code-backend.txt

# Duplicate code
pylint src/ --disable=all --enable=duplicate-code --output-format=json > ../analysis/duplicate-code-backend.json

# Security analysis
bandit -r src/ -f json -o ../analysis/bandit-security.json
```

### 1.2 Analyze Metrics

**Calculate baseline metrics**:
```markdown
# Baseline Metrics (Before Refactoring)

## Code Size
- Frontend LoC: [total]
- Backend LoC: [total]
- Test LoC: [total]
- Production/Test Ratio: [ratio]

## Complexity
- Average Cyclomatic Complexity: [number]
- Max Cyclomatic Complexity: [number] in [file:line]
- Maintainability Index: [score]

## Quality
- ESLint Issues: [count] (Critical: X, High: Y, Medium: Z)
- Ruff Issues: [count]
- MyPy Errors: [count]
- Security Issues: [count]

## Test Coverage
- Frontend: [%]
- Backend: [%]
- Overall: [%]

## Code Duplication
- Frontend: [%] duplicated code
- Backend: [%] duplicated code
- Largest duplicate: [lines] in [files]

## Dependencies
- Frontend: [count] packages
- Backend: [count] packages
- Unused: [count]
```

**Deliverable**: `analysis/baseline-metrics.md`

---

## 🎯 PHASE 2: REFACTORING STRATEGY (60 minutes)

### 2.1 Prioritize Refactoring Tasks

**Categorize all identified issues**:

#### Category 1: Critical (Breaks Clean Architecture)
- Layer violations (e.g., UI calling database directly)
- Missing dependency injection
- Hardcoded secrets/config
- Security vulnerabilities
- **Priority**: HIGHEST - Fix first

#### Category 2: High (Significant Code Smells)
- God classes (>300 lines)
- Long functions (>50 lines)
- Cyclomatic complexity >10
- Deep nesting (>3 levels)
- Duplicate code (>20 lines duplicated)
- **Priority**: HIGH - Fix after critical

#### Category 3: Medium (Maintainability Issues)
- Poor naming conventions
- Missing documentation
- Commented-out code
- Magic numbers
- Inconsistent patterns
- **Priority**: MEDIUM - Fix after high

#### Category 4: Low (Cosmetic)
- Formatting inconsistencies
- Import order
- Whitespace
- **Priority**: LOW - Fix last (or auto-fix)

### 2.2 Create Refactoring Roadmap

**Template**:
```markdown
# Refactoring Roadmap

## Wave 1: Critical Architecture Fixes (Est: [hours])
1. **[Issue Title]**
   - Location: [file:line]
   - Problem: [description]
   - Impact: [why critical]
   - Solution: [refactoring approach]
   - Tests affected: [list]
   - Estimated time: [minutes]

## Wave 2: Code Smell Elimination (Est: [hours])
[Same format]

## Wave 3: Maintainability Improvements (Est: [hours])
[Same format]

## Wave 4: Cosmetic Cleanup (Est: [hours])
[Same format]

## Total Estimated Time: [hours]
```

**Deliverable**: `analysis/refactoring-roadmap.md`

**Note**: For infrastructure refactoring (GitHub Workflows, CI/CD optimization, Docker improvements), refer to **CODEBASE_CLEANUP_AGENT_PROMPT.md Section 2.7**.

---

## 🔨 PHASE 3: REFACTORING EXECUTION (Test-Driven!)

### 3.1 The Refactoring Loop (MANDATORY PROCESS)

**For EVERY single refactoring task, follow this loop**:

```
1. ✅ VERIFY TESTS GREEN
   ├─ Run all tests: pytest --cov, npm test
   └─ All pass? → Continue. Any fail? → FIX FIRST!

2. 📖 READ CODE CONTEXT
   ├─ Read target file completely
   ├─ Read all files that import it
   ├─ Read all files it imports
   └─ Understand dependencies

3. 🧪 WRITE CHARACTERIZATION TESTS (if coverage <100% for target code)
   ├─ Test current behavior (even if ugly)
   ├─ Ensure tests are deterministic
   └─ Run tests: ALL GREEN?

4. 🔧 MAKE ONE SMALL REFACTORING
   ├─ Change ONE thing (extract function, rename, move)
   ├─ Keep change <50 lines
   └─ Preserve external behavior

5. ✅ RUN TESTS IMMEDIATELY
   ├─ Run affected tests first (fast feedback)
   ├─ Run full suite (ensure no side effects)
   └─ All green? → Continue. Red? → REVERT and try different approach!

6. 📝 COMMIT ATOMICALLY
   ├─ git add [changed files]
   ├─ git commit -m "refactor: [clear description]"
   └─ ONE commit per refactoring step

7. 🔁 REPEAT until target file is clean
```

**NEVER**:
- ❌ Make multiple changes before running tests
- ❌ Skip tests to "save time" or because they're "too hard to write"
- ❌ Avoid large refactorings because they're "complex" - DO THE WORK!
- ❌ Settle for "good enough" - User expects EXCELLENCE
- ❌ Commit broken code ("I'll fix it later")
- ❌ Batch multiple refactorings in one commit
- ❌ Give up on refactoring because it's "taking too long"

**ALWAYS**:
- ✅ Run tests after EVERY change
- ✅ Commit when tests are green
- ✅ Revert immediately if tests fail unexpectedly

### 3.2 Specific Refactoring Techniques

#### Technique 1: Extract Method

**When**: Function >50 lines or doing >1 thing

**Process**:
1. Identify coherent block of code (10-20 lines)
2. Check dependencies (what variables needed?)
3. Write test for NEW function first (TDD!)
4. Extract to new function
5. Run tests → GREEN?
6. Commit: `refactor: extract [new_function_name] from [old_function]`

**Example**:
```python
# BEFORE (God function)
async def sync_devices(repo):
    # 80 lines of mixed concerns
    discovered = await discover()
    for device in discovered:
        info = await get_device_info(device.ip)
        await repo.upsert(Device(**info))
    return discovered

# AFTER (clean separation)
async def sync_devices(repo):
    discovered = await discover_devices()
    await persist_devices(discovered, repo)
    return discovered

async def discover_devices() -> list[DiscoveredDevice]:
    """Discover SoundTouch devices on network."""
    return await discover()

async def persist_devices(devices: list[DiscoveredDevice], repo: DeviceRepository):
    """Fetch device info and save to repository."""
    for device in devices:
        info = await fetch_device_info(device.ip)
        await repo.upsert(Device(**info))
```

#### Technique 2: Replace Magic Numbers with Constants

**When**: Hardcoded values like `if timeout > 30:`

**Process**:
1. Identify all magic numbers in file
2. Create constants module (if not exists)
3. Define named constant: `DEVICE_DISCOVERY_TIMEOUT_SEC = 30`
4. Replace magic number with constant
5. Run tests → GREEN?
6. Commit: `refactor: replace magic numbers with named constants`

#### Technique 3: Eliminate Duplication

**When**: Same code appears >2 times

**Process**:
1. Find largest duplicate block (use jscpd/pylint output)
2. Write test for extracted function (TDD!)
3. Extract to shared utility/helper
4. Replace first occurrence → tests GREEN?
5. Replace second occurrence → tests GREEN?
6. Replace remaining occurrences one at a time
7. Commit: `refactor: deduplicate [functionality] into [utility_name]`

#### Technique 4: Simplify Conditional Logic

**When**: Nested if/else >3 levels

**Process**:
1. Write tests covering all branches
2. Apply guard clauses (early returns)
3. Extract complex conditions to named functions
4. Use polymorphism for type-based branching
5. Tests GREEN after each step?
6. Commit: `refactor: simplify conditional logic in [function_name]`

**Example**:
```python
# BEFORE (nested hell)
def get_status(device):
    if device:
        if device.is_connected:
            if device.is_playing:
                return "playing"
            else:
                return "connected"
        else:
            return "disconnected"
    else:
        return "unknown"

# AFTER (guard clauses)
def get_status(device):
    if not device:
        return "unknown"
    
    if not device.is_connected:
        return "disconnected"
    
    return "playing" if device.is_playing else "connected"
```

#### Technique 5: Dependency Injection

**When**: Class creates its own dependencies

**Process**:
1. Identify hidden dependencies (e.g., `self.client = HttpClient()`)
2. Add parameter to constructor
3. Update all callers (one at a time!)
4. Update tests to inject mock
5. Tests GREEN after each caller update?
6. Commit: `refactor: inject [dependency] into [class_name]`

#### Technique 6: Naming Conventions & Consistency

**When**: Inconsistent naming across codebase (camelCase mixed with snake_case, etc.)

**Why Critical**: Naming inconsistencies create cognitive load, hide bugs, and violate language conventions.

**ZWINGEND**: Konsistente Namensgebung über ALLE Code-Dateien hinweg!

##### Python Backend (PEP 8)

**Correct Conventions**:
```python
# ✅ GOOD: PEP 8 Konventionen
class DeviceRepository:           # PascalCase für Klassen
    def get_by_device_id(self):   # snake_case für Funktionen/Methoden
        pass

SSDP_MULTICAST_ADDR = "..."      # UPPER_SNAKE_CASE für Konstanten
device_count = 5                  # snake_case für Variablen
_internal_cache = {}              # Leading underscore für private

# ❌ BAD: Inkonsistent
class deviceRepository:           # Falsch! PascalCase fehlt
    def GetDeviceById(self):      # Falsch! camelCase statt snake_case
        MAX_devices = 10          # Falsch! Inkonsistent
```

##### TypeScript/JavaScript Frontend

**Correct Conventions**:
```typescript
// ✅ GOOD: Standard JS/TS Konventionen
class DeviceManager {             // PascalCase für Klassen
  fetchDevices() {}               // camelCase für Methoden
}

const MAX_RETRY_COUNT = 3;        // UPPER_SNAKE_CASE für Konstanten
let deviceList = [];              // camelCase für Variablen
const _privateHelper = () => {};  // Leading underscore für private

// React Components: PascalCase
function DeviceCard({ device }) { return <div>...</div>; }

// ❌ BAD: Inkonsistent
function device_card() {}         // Falsch! Components PascalCase
let DeviceList = [];              // Falsch! Variablen camelCase
const max_retry = 3;              // Falsch! Konstanten UPPER_SNAKE_CASE
```

##### File Naming

**Correct Conventions**:
```
# ✅ GOOD: Konsistente Konventionen

Backend Python:
  adapter.py                      # snake_case für Module
  device_repository.py            # snake_case mit Unterstrichen
  test_adapter.py                 # test_ Präfix für Tests

Frontend JavaScript/TypeScript:
  DeviceCard.jsx                  # PascalCase für React Components
  deviceService.ts                # camelCase für Services/Utils
  DeviceCard.test.jsx             # .test. für Tests

# ❌ BAD: Inkonsistent
  Device_Repository.py            # Falsch! Keine PascalCase für Python-Module
  device-card.jsx                 # Falsch! Kebab-case vermeiden
  devicecard.jsx                  # Falsch! Keine Trennung erkennbar
```

##### API Endpoints & URLs

**Correct Conventions**:
```python
# ✅ GOOD: RESTful mit kebab-case
@router.get("/api/devices")                    # Plural für Collections
@router.get("/api/devices/{device_id}")        # snake_case für Parameter
@router.post("/api/settings/manual-ips")       # kebab-case für Multi-Word

# ❌ BAD: Inkonsistent
@router.get("/api/Device")                     # Falsch! Singular + PascalCase
@router.get("/api/devices/{deviceId}")         # Falsch! camelCase in URL
@router.post("/api/settings/manualIPs")        # Falsch! camelCase statt kebab
```

##### Environment Variables & Config

**Correct Conventions**:
```bash
# ✅ GOOD: UPPER_SNAKE_CASE mit Namespace-Präfix
CT_DISCOVERY_TIMEOUT=10
CT_MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101
CT_LOG_LEVEL=DEBUG

# ❌ BAD: Inkonsistent oder ohne Präfix
discoveryTimeout=10               # Falsch! Kein UPPER_SNAKE_CASE
ct-manual-ips=...                 # Falsch! Kebab-case statt Underscore
TIMEOUT=10                        # Falsch! Kein CT_ Präfix (Kollisionsgefahr)
```

##### Database Fields

**Correct Conventions**:
```python
# ✅ GOOD: snake_case konsistent
class Device:
    device_id: str                # snake_case
    ip_address: str
    friendly_name: str
    created_at: datetime

# ❌ BAD: Inkonsistent
class Device:
    deviceId: str                 # Falsch! camelCase in Python
    IPAddress: str                # Falsch! PascalCase
    FriendlyName: str             # Falsch! PascalCase
```

##### Boolean Variables & Flags

**Correct Conventions**:
```python
# ✅ GOOD: is_, has_, should_, can_ Präfixe
is_connected = True
has_error = False
should_retry = True
can_discover = False

# ❌ BAD: Verb oder Substantiv
connected = True                  # Unklar: Status oder Aktion?
error = False                     # Unklar: Boolean oder Error-Objekt?
retry = True                      # Unklar: Boolean oder Retry-Count?
```

##### Event Handlers & Callbacks

**Correct Conventions**:
```typescript
// ✅ GOOD: on/handle Präfixe
function handleClick(event) {}
function onDeviceSelected(device) {}
function handleRetry() {}

// ❌ BAD: Kein Präfix
function click() {}               // Unklar: Handler oder Aktion?
function deviceSelected() {}      // Unklar: Handler oder Getter?
```

##### Naming Consistency Checklist

**Vor jedem Commit prüfen**:
- [ ] Python: snake_case (Funktionen/Variablen), PascalCase (Klassen), UPPER_SNAKE_CASE (Konstanten)
- [ ] TypeScript/React: camelCase (Funktionen/Variablen), PascalCase (Klassen/Components), UPPER_SNAKE_CASE (Konstanten)
- [ ] Dateinamen: snake_case (Python), camelCase/PascalCase (JS/TS je nach Typ)
- [ ] API-Endpoints: kebab-case, Plural für Collections
- [ ] Env-Variablen: CT_ Präfix + UPPER_SNAKE_CASE
- [ ] Boolean: is_/has_/should_/can_ Präfixe
- [ ] Event Handler: handle/on Präfixe
- [ ] Private: Leading underscore `_`
- [ ] Keine Abbreviations (außer allgemein bekannt: HTTP, URL, IP, ID)
- [ ] Sprechende Namen statt Kürzel (discovery statt disc, timeout statt to)

##### Anti-Patterns vermeiden

**VERBOTEN**:
```python
# ❌ NEVER USE THESE
temp, tmp, data, info, obj       # Zu generisch
a, b, c, x, y, z                 # Single-letter (außer in Loops/Math)
get_data(), do_stuff()           # Nicht-deskriptiv
myVar, theDevice, aDevice        # Artikel-Präfixe
deviceManager2, device_final     # Nummerierung/Suffixe
```

**Refactoring Process**:
1. Scan file for naming violations (use checklist above)
2. Rename ONE symbol at a time (use IDE rename refactoring if possible)
3. Run tests after each rename → GREEN?
4. Commit: `refactor: rename [old_name] to [new_name] for consistency`
5. Repeat for next violation

**Bei Unsicherheit**: Bestehende Code-Patterns nachahmen, nicht neue Stile erfinden!

### 3.3 Refactoring Execution Checklist

**Before starting refactoring**:
- [ ] All tests are GREEN
- [ ] Baseline metrics documented
- [ ] Refactoring roadmap approved
- [ ] Git working directory clean

**During refactoring (per task)**:
- [ ] Read target code + context (entire files)
- [ ] Write characterization tests if needed
- [ ] Make ONE small change
- [ ] Run tests immediately
- [ ] Tests GREEN? → Commit. RED? → Revert
- [ ] Update refactoring roadmap (mark complete)

**After each wave**:
- [ ] All tests GREEN
- [ ] No regressions in E2E tests
- [ ] Code metrics improved (check with tools)
- [ ] Documentation updated if needed
- [ ] User informed of progress

---

## 📊 PHASE 4: CONTINUOUS VALIDATION (Ongoing)

### 4.1 Test Execution Strategy

**Run tests at THREE levels**:

#### Level 1: Unit Tests (Fast - Run after EVERY change)
```powershell
# Frontend (affected files only)
npm test -- --changed --coverage

# Backend (affected module only)
pytest tests/unit/[module]/ -v

# Should complete in <10 seconds
```

#### Level 2: Integration Tests (Medium - Run after completing a file)
```powershell
# Frontend
npm test -- tests/integration/

# Backend
pytest tests/integration/ -v

# Should complete in <60 seconds
```

#### Level 3: E2E Tests (Slow - Run after completing a wave)
```powershell
# Frontend
npm run test:e2e

# Backend
pytest tests/e2e/ -v

# Can take several minutes
```

### 4.2 Coverage Requirements

**MANDATORY Coverage Thresholds**:
- ✅ Overall: ≥80%
- ✅ Refactored modules: ≥90%
- ✅ Critical paths: 100%

**After each refactoring task**:
```powershell
# Check coverage
pytest --cov=src --cov-report=term-missing --cov-fail-under=80

# If coverage DROPS → Write missing tests BEFORE continuing!
```

### 4.3 Test Quality Requirements

⚠️ **CRITICAL**: Coverage is NOT the goal - MEANINGFUL TESTS are the goal!

**Test Quality Standards**:

#### Tests MUST Test Functionality, Not Just Exist
- ❌ **BAD**: Tests that only check `assert result is not None` (useless!)
- ❌ **BAD**: Tests that just call functions without assertions (coverage theater)
- ❌ **BAD**: Tests that mock everything and test nothing (fake coverage)
- ✅ **GOOD**: Tests that verify actual business logic and edge cases

**Example of BAD test (coverage theater)**:
```python
def test_sync_devices():
    """Test device sync."""
    repo = Mock()
    service = DeviceService(repo)
    service.sync()  # No assertions! Just calls the function
    # This gives coverage but tests NOTHING!
```

**Example of GOOD test (tests functionality)**:
```python
def test_sync_devices_saves_discovered_devices():
    """Test that discovered devices are saved to repository."""
    # Arrange
    mock_discovery = Mock(return_value=[
        Device(id="123", name="Living Room"),
        Device(id="456", name="Kitchen")
    ])
    mock_repo = Mock()
    service = DeviceService(repo=mock_repo, discovery=mock_discovery)
    
    # Act
    service.sync()
    
    # Assert - Verify actual behavior!
    assert mock_repo.upsert.call_count == 2
    mock_repo.upsert.assert_any_call(Device(id="123", name="Living Room"))
    mock_repo.upsert.assert_any_call(Device(id="456", name="Kitchen"))
```

#### Required Test Scenarios for Each Function

**For EVERY public function, test**:
1. **Happy Path**: Normal input → expected output
2. **Edge Cases**: Empty inputs, null, zero, max values
3. **Error Cases**: Invalid input → proper exception/error handling
4. **Side Effects**: Database changes, API calls, state mutations verified
5. **Business Logic**: All conditional branches executed with assertions

**Example - Testing volume control**:
```python
# ✅ Complete test suite for volume control
def test_set_volume_normal_range():
    """Test setting volume within valid range (0-100)."""
    assert set_volume(50) == 50

def test_set_volume_zero():
    """Test volume can be set to minimum (0)."""
    assert set_volume(0) == 0

def test_set_volume_max():
    """Test volume can be set to maximum (100)."""
    assert set_volume(100) == 100

def test_set_volume_negative_raises_error():
    """Test negative volume raises ValueError."""
    with pytest.raises(ValueError, match="Volume must be 0-100"):
        set_volume(-1)

def test_set_volume_above_max_raises_error():
    """Test volume >100 raises ValueError."""
    with pytest.raises(ValueError, match="Volume must be 0-100"):
        set_volume(101)

def test_set_volume_calls_device_api():
    """Test that setting volume calls device API with correct value."""
    mock_device = Mock()
    set_volume(50, device=mock_device)
    mock_device.set_volume.assert_called_once_with(50)
```

#### Code Must Be Written to Be Testable

**Design for Testability**:
- ✅ Use **Dependency Injection** (pass dependencies as constructor args)
- ✅ **Separate side effects** from business logic (pure functions)
- ✅ **Small functions** (<20 lines) are easier to test
- ✅ **Single Responsibility** - one function does one thing
- ❌ **No global state** (makes tests non-deterministic)
- ❌ **No tight coupling** (hard to mock dependencies)
- ❌ **No hidden dependencies** (instantiating dependencies inside functions)

**Example - Hard to Test (BAD)**:
```python
class DeviceSync:
    def sync(self):
        # Hidden dependencies = UNTESTABLE!
        client = BoseClient()  # Can't mock
        db = Database()        # Can't mock
        devices = client.discover()
        db.save(devices)
```

**Example - Easy to Test (GOOD)**:
```python
class DeviceSync:
    def __init__(self, client: BoseClient, db: Database):
        # Dependency Injection = TESTABLE!
        self.client = client
        self.db = db
    
    def sync(self):
        devices = self.client.discover()
        self.db.save(devices)

# Now testing is trivial:
def test_sync():
    mock_client = Mock(return_value=[Device(...)])
    mock_db = Mock()
    sync = DeviceSync(client=mock_client, db=mock_db)
    sync.sync()
    # Verify actual behavior:
    assert mock_db.save.called
    assert mock_db.save.call_args[0][0][0].id == "123"
```

#### When Coverage Is NOT Enough

**These scenarios indicate BAD tests despite high coverage**:
1. **No assertions** - Test runs code but doesn't verify anything
2. **Only happy path tested** - No edge cases or errors tested
3. **Mocking too much** - Mock returns are tested, not actual logic
4. **Tests pass when code is broken** - Tests don't catch real bugs
5. **Tests are fragile** - Break on every refactoring (testing implementation, not behavior)

**Quality Check Questions**:
- ❓ If I delete this assertion, does the test still pass? → BAD TEST
- ❓ If I break the business logic, does the test fail? → If NO: BAD TEST
- ❓ Does this test verify a real user requirement? → If NO: USELESS TEST
- ❓ Can I understand what's being tested from the test name? → If NO: UNCLEAR TEST

#### Regression Tests Are MANDATORY

**For EVERY bug fixed**:
1. Write a test that reproduces the bug (RED)
2. Fix the bug (GREEN)
3. **Keep the test** as regression protection (prevent future recurrence)

**Example**:
```python
def test_xml_namespace_parsing_regression():
    """Regression test for XML namespace handling bug.
    
    Bug: SSDP discovery failed to parse manufacturer from XML with namespace.
    Fixed: 2026-01-29 - Implemented namespace-agnostic search.
    """
    xml = '<root xmlns="urn:schemas-upnp-org:device-1-0"><manufacturer>Bose</manufacturer></root>'
    result = parse_manufacturer(xml)
    assert result == "Bose"  # Would fail before fix
```

#### Agent Responsibilities

**When writing tests, you MUST**:
- ✅ Verify actual behavior with specific assertions
- ✅ Test all code paths (if/else, try/except, loops)
- ✅ Test edge cases and error conditions
- ✅ Use descriptive test names explaining WHAT is tested
- ✅ Write tests that fail when code breaks (verify this!)
- ✅ Prefer testing behavior over implementation details

**NEVER**:
- ❌ Write tests just to increase coverage percentage
- ❌ Write tests without assertions (coverage theater)
- ❌ Skip edge cases because "happy path works"
- ❌ Accept "this is hard to test" - REFACTOR until testable!
- ❌ Mock so much that you're testing the mocks, not the code

**REMEMBER**: 80% coverage with meaningful tests > 100% coverage with useless tests!

### 4.4 Regression Detection

**Signs of regression**:
- ❌ Test that was passing now fails
- ❌ Test coverage decreased
- ❌ E2E test fails intermittently (flaky)
- ❌ Application behavior changed unexpectedly

**Response to regression**:
1. **STOP refactoring immediately**
2. **Analyze** which change broke it (`git log --oneline -10`)
3. **Revert** to last known good state (`git revert [commit]`)
4. **Fix** root cause (don't mask with try-catch!)
5. **Add test** to prevent future regression
6. **Resume** refactoring

---

## 🧹 PHASE 5: CLEANUP & POLISH (30 minutes)

### 5.1 Remove Dead Code

**Process**:
```powershell
# Frontend
npx unimported
# Delete files that are never imported

# Backend
vulture src/
# Delete functions/classes with 0% confidence usage

# Verify nothing breaks
npm test
pytest
```

### 5.2 Fix Formatting

**Auto-fix formatting issues**:
```powershell
# Frontend
npx prettier --write "src/**/*.{js,jsx,css}"
npx eslint src/ --fix

# Backend
black src/ tests/
isort src/ tests/
ruff check src/ tests/ --fix
```

### 5.3 Update Documentation

**Check if docs need updates**:
```markdown
# Documentation Review Checklist

## Code Comments
- [ ] Remove obsolete comments (code is self-explanatory now?)
- [ ] Update comments that describe old behavior
- [ ] Add docstrings for public APIs

## README files
- [ ] Update setup instructions if dependencies changed
- [ ] Update examples if API changed
- [ ] Update architecture docs if structure changed

## API Documentation
- [ ] OpenAPI schema up-to-date (FastAPI auto-generated)
- [ ] Component prop types documented (React)
```

---

## 📈 PHASE 6: FINAL VALIDATION & REPORT (60 minutes)

### 6.1 Run Complete Test Suite

**Full validation**:
```powershell
# Frontend
cd frontend
npm run lint                  # 0 errors
npm run test:coverage         # >80%
npm run test:e2e             # All pass
npm run build                # Successful

# Backend
cd backend
ruff check src/              # 0 errors
mypy src/ --strict           # 0 type errors
pytest --cov=src --cov-fail-under=80 --cov-branch
pytest tests/e2e/            # All pass
```

### 6.2 Re-run Static Analysis

**Compare metrics before/after**:
```powershell
# Re-run all tools from Phase 1
# Save outputs to analysis/after-refactoring/

# Generate diff report
```

### 6.3 Generate Final Report

**Template**:
```markdown
# Refactoring Report - CloudTouch

**Date**: [YYYY-MM-DD]
**Duration**: [total hours]
**Commits**: [count]
**Status**: ✅ COMPLETE

---

## Executive Summary

[2-3 sentence overview of what was refactored and why]

---

## Metrics Comparison

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Code Size** | | | |
| Frontend LoC | [N] | [M] | [+/- X%] |
| Backend LoC | [N] | [M] | [+/- X%] |
| **Complexity** | | | |
| Avg Cyclomatic Complexity | [N] | [M] | [+/- X%] |
| Max Cyclomatic Complexity | [N] | [M] | [+/- X%] |
| Maintainability Index | [N] | [M] | [+/- X%] |
| **Quality** | | | |
| Linting Errors | [N] | 0 | -100% |
| Type Errors | [N] | 0 | -100% |
| Security Issues | [N] | 0 | -100% |
| **Coverage** | | | |
| Frontend Coverage | [N%] | [M%] | [+X%] |
| Backend Coverage | [N%] | [M%] |  [+X%] |
| **Duplication** | | | |
| Frontend Duplicates | [N%] | [M%] | [+/- X%] |
| Backend Duplicates | [N%] | [M%] | [+/- X%] |

---

## Refactoring Tasks Completed

### Wave 1: Critical Architecture Fixes ([N] tasks)
1. ✅ [Task description] - [commit hash]
2. ✅ [...]

### Wave 2: Code Smell Elimination ([N] tasks)
[...]

### Wave 3: Maintainability Improvements ([N] tasks)
[...]

### Wave 4: Cosmetic Cleanup ([N] tasks)
[...]

**Total**: [N] tasks completed

---

## Key Improvements

### Frontend
- **Reduced complexity**: Extracted [N] god functions into smaller units
- **Eliminated duplication**: Removed [N] lines of duplicate code
- **Improved structure**: [specific architectural improvement]
- **Test coverage**: +[X]% (now at [Y]%)

### Backend
- **Fixed architecture violations**: [specific fixes]
- **Simplified logic**: Reduced max complexity from [N] to [M]
- **Enhanced type safety**: [N] type hints added, 0 MyPy errors
- **Test coverage**: +[X]% (now at [Y]%)

---

## Files Modified

**Total files changed**: [N]

### Most Significant Changes
1. `[file path]` - [description of refactoring]
2. `[file path]` - [description]
3. [...]

---

## Test Results

### Unit Tests
- Frontend: [X] tests, all passing
- Backend: [Y] tests, all passing

### Integration Tests
- Frontend: [X] tests, all passing
- Backend: [Y] tests, all passing

### E2E Tests
- Cypress: [X] scenarios, all passing
- Backend E2E: [Y] scenarios, all passing

**Total Test Execution Time**: [minutes]

---

## Remaining Technical Debt

### Accepted Trade-offs
1. [Description] - Reason: [justification]
2. [...]

### Future Work (Backlog)
1. [Description] - Estimated effort: [hours]
2. [...]

---

## Commits Summary

**Branch**: `refactor/[date]`
**Total Commits**: [N]
**Commit Message Format**: Conventional Commits (refactor, fix, test, docs)

### Sample Commits
```
refactor(frontend): extract device list rendering logic
refactor(backend): inject SSDPDiscovery into DeviceAdapter
test(frontend): add missing edge cases for DeviceImage
fix(backend): correct async error handling in sync_devices
docs: update architecture diagram after refactoring
```

---

## Quality Gates Status

- [x] All linters pass (0 errors)
- [x] All type checkers pass (0 errors)
- [x] All tests pass (100% success rate)
- [x] Coverage ≥80% overall, ≥90% for refactored modules
- [x] No security vulnerabilities
- [x] E2E tests pass
- [x] Build successful
- [x] No regressions detected

---

## Lessons Learned

### What Went Well
- [Insight 1]
- [Insight 2]

### What Could Be Improved
- [Insight 1]
- [Insight 2]

### Recommendations for Future Refactoring
- [Recommendation 1]
- [Recommendation 2]

---

**Next Steps**: Ready for code review and merge to main branch.
```

**Deliverable**: `analysis/refactoring-final-report.md`

---

## 🚨 EXCEPTION HANDLING

### Exception 1: Tests Fail During Refactoring

**Scenario**: You make a change, tests turn red.

**Response**:
1. **STOP immediately** - Do NOT continue refactoring
2. **Analyze failure**:
   - Is it a true regression? → REVERT change
   - Is test relying on implementation detail? → FIX TEST (test behavior, not implementation)
   - Is test flaky? → FIX TEST (remove race conditions, hardcoded waits)
3. **Fix root cause** - Never mask with try-catch or skip test
4. **Verify fix** - Run tests 5 times, all must pass
5. **Document** - Add comment explaining what was fixed
6. **Resume refactoring**

**NEVER**:
- ❌ Skip failing test (`@pytest.mark.skip`, `test.skip()`)
- ❌ Mark as expected failure (`xfail`)
- ❌ Lower coverage threshold
- ❌ Continue refactoring with red tests

### Exception 2: Refactoring Reveals Fundamental Design Flaw

**Scenario**: You realize the architecture is fundamentally broken.

**Response**:
1. **STOP refactoring**
2. **Document the issue**:
   ```markdown
   # CRITICAL DESIGN ISSUE DISCOVERED
   
   ## Problem
   [Detailed description of architectural flaw]
   
   ## Evidence
   [Code examples, dependencies diagram showing circular deps, etc.]
   
   ## Impact
   - Current: [how it affects current code]
   - Refactoring: [why it blocks refactoring]
   
   ## Proposed Solutions
   ### Option 1: [Approach]
   - Pros: [...]
   - Cons: [...]
   - Estimated effort: [hours/days]
   
   ### Option 2: [Approach]
   - Pros: [...]
   - Cons: [...]
   - Estimated effort: [hours/days]
   
   ## Recommendation
   [Which option and why]
   
   ## Next Steps
   USER APPROVAL REQUIRED before proceeding
   ```
3. **Present to user** - Wait for decision
4. **DO NOT** attempt to fix without approval
5. **DO NOT** work around the issue

### Exception 3: Coverage Drops Below Threshold

**Scenario**: After refactoring, coverage is 78% (was 85%).

**Response**:
1. **STOP refactoring**
2. **Identify uncovered code**:
   ```powershell
   pytest --cov=src --cov-report=term-missing
   # Shows which lines are not covered
   ```
3. **Write missing tests**:
   - For refactored code: Write tests for new functions
   - For existing code: Add tests for edge cases
4. **Verify coverage back above 80%**
5. **Resume refactoring**

**Root Cause Analysis**:
- Did refactoring introduce untested code paths?
- Were tests deleted accidentally?
- Did code restructuring expose gaps?

### Exception 4: Can't Find Clean Refactoring Path

**Scenario**: Every approach you try breaks tests or increases complexity.

**Response**:
1. **STOP and reflect**
2. **Re-read the code** - Maybe you misunderstood the intent
3. **Check git history** - `git log -p [file]` to see why code was written this way
4. **Consult tests** - What behavior is required?
5. **Try different technique**:
   - Extract Method not working? → Try Extract Class
   - Simplifying conditions failing? → Try Strategy Pattern
   - Can't reduce complexity? → Maybe it's inherent complexity (domain complexity)
6. **Document and move on**:
   ```markdown
   # REFACTORING DEFERRED: [file:line]
   
   ## Attempted Approaches
   1. [Approach 1] - Failed because [reason]
   2. [Approach 2] - Failed because [reason]
   
   ## Current Code
   [Code snippet]
   
   ## Why It's Complex
   [Explanation - is it essential complexity or accidental?]
   
   ## Recommendation
   Accept current complexity OR plan larger refactoring (separate PR)
   ```

### Exception 5: Refactoring Taking Longer Than Estimated

**Scenario**: Estimated 2 hours, already spent 5 hours.

**Response**:
1. **Assess progress**:
   - What % of roadmap complete?
   - Are tests still green?
   - Is code quality improving?
2. **Re-estimate remaining work**
3. **Communicate to user**:
   ```
   Progress update:
   - Completed: [N] tasks ([X]% of roadmap)
   - Time spent: [hours]
   - Remaining: [M] tasks (est. [Y] hours)
   - Issues encountered: [brief summary]
   
   Continue or pause for review?
   ```
4. **Get user decision** - Continue, pause, or adjust scope

**NEVER**:
- ❌ Rush through remaining work (quality > speed)
- ❌ Skip tests to "catch up"
- ❌ Leave refactoring half-done without communication

### Exception 6: "This Code is Too Hard to Test"

**Scenario**: You encounter code that's difficult to write tests for.

**Response**:
1. **RECOGNIZE**: Hard to test = BAD DESIGN (tight coupling, hidden dependencies, etc.)
2. **DO NOT SKIP THE TEST!**
3. **Refactor to make testable FIRST**:
   - Extract dependencies to constructor (Dependency Injection)
   - Break up god classes into smaller units
   - Separate side effects from pure logic
   - Use adapter pattern for external systems
4. **Write the test** - Should be easier now
5. **Continue refactoring**

**Example**:
```python
# HARD TO TEST (tight coupling)
class DeviceSync:
    def sync(self):
        client = BoseClient()  # Hard to mock!
        devices = client.discover()
        db = Database()  # Hard to mock!
        db.save(devices)

# EASY TO TEST (dependency injection)
class DeviceSync:
    def __init__(self, client: BoseClient, db: Database):
        self.client = client
        self.db = db
    
    def sync(self):
        devices = self.client.discover()
        self.db.save(devices)

# Now test is trivial:
def test_sync():
    mock_client = Mock()
    mock_db = Mock()
    sync = DeviceSync(mock_client, mock_db)
    sync.sync()
    assert mock_db.save.called
```

**NEVER**:
- ❌ Skip test because "it's too complex"
- ❌ Say "this code is untestable" (ALL code is testable with right design)
- ❌ Accept poor design just to avoid refactoring work

**REMEMBER**: If it's hard to test, the design is WRONG. Fix the design.

### Exception 7: "This Refactoring is Too Big"

**Scenario**: Refactoring requires changing 50+ files, estimated 20+ hours.

**Response**:
1. **DO NOT AVOID IT!** - Big refactorings are sometimes necessary
2. **Break into phases**:
   - Phase 1: Add new abstraction (tests green)
   - Phase 2: Migrate module A (tests green)
   - Phase 3: Migrate module B (tests green)
   - ...
   - Phase N: Remove old code (tests green)
3. **Use Strangler Fig pattern**:
   - New code lives alongside old
   - Gradually migrate callers
   - Delete old code when nothing uses it
4. **Communicate scope**:
   ```
   Large refactoring required: [description]
   
   Scope:
   - Files affected: [N]
   - Estimated effort: [hours]
   - Phases: [M]
   
   Impact:
   - Reduces complexity by [X]%
   - Eliminates [Y] code smells
   - Improves testability
   
   Proceed? (User approval required for >20 hour refactorings)
   ```
5. **Execute systematically** - One phase at a time, tests green between phases

**NEVER**:
- ❌ Say "this is too big, let's skip it" (UNACCEPTABLE!)
- ❌ Take shortcuts to reduce scope (quality > effort)
- ❌ Leave half-migrated code (finish what you start)

**REMEMBER**: User values QUALITY over agent convenience. DO THE WORK.

---

## 🚫 ANTI-LAZINESS ENFORCEMENT

### Detecting Agent Laziness

**Signs you're being lazy**:
- 🚩 Thinking "this test is too hard, I'll skip it"
- 🚩 Thinking "this refactoring is too big, I'll avoid it"
- 🚩 Thinking "good enough" instead of "excellent"
- 🚩 Avoiding dependency injection because "it's complicated"
- 🚩 Leaving TODO comments instead of fixing issues
- 🚩 Skipping edge cases in tests
- 🚩 Not reading code line-by-line (skimming instead)

### Agent Self-Check Questions

**Before skipping anything, ask**:
1. "Am I avoiding this because it's genuinely impossible, or just hard?"
   - Hard ≠ Impossible. DO THE HARD THING.
2. "Will this shortcut reduce code quality?"
   - YES? → Don't take the shortcut.
3. "Would I accept this quality from a human developer?"
   - NO? → Higher standard for yourself.
4. "Am I optimizing for my convenience or user's benefit?"
   - User's benefit ALWAYS wins.

### Acceptable Reasons to Skip/Defer

**ONLY these reasons are valid**:
- ✅ Requires fundamental architecture change (needs user approval)
- ✅ Depends on external library change (can't control)
- ✅ Would break existing API contracts (requires user decision)
- ✅ Discovered after 10+ honest attempts with different approaches

**NOT acceptable reasons**:
- ❌ "It's too complex" - Complexity is WHY it needs refactoring!
- ❌ "It would take too long" - Quality takes time!
- ❌ "The test is too hard to write" - Make code testable!
- ❌ "I don't understand the code" - READ IT AGAIN!
- ❌ "It's not that bad" - User expects EXCELLENCE!

### Accountability

**If you skip/defer something**:
1. Document it thoroughly (see Exception 4)
2. Explain ALL attempted approaches
3. Provide concrete evidence it's truly impossible (not just hard)
4. Propose alternative solution
5. Get user approval

**User will review your work. Laziness will be detected and rejected.**

---

## ✅ SUCCESS CRITERIA

**Refactoring is COMPLETE when**:

### Code Quality
- [x] Cyclomatic complexity: avg <5, max <10
- [x] Function length: avg <20 lines, max <50
- [x] Class length: max 300 lines
- [x] Duplication: <3%
- [x] No god classes, no long methods
- [x] All magic numbers replaced with constants
- [x] No commented-out code

### Architecture
- [x] Clean Architecture layers respected
- [x] Dependencies flow inward (outer → inner)
- [x] Dependency injection used consistently
- [x] No circular dependencies
- [x] Adapters wrap all external systems

### Tests
- [x] All tests pass (100% success rate)
- [x] Coverage ≥80% overall
- [x] Coverage ≥90% for refactored modules
- [x] No flaky tests (5 runs, all pass)
- [x] Test execution time acceptable (<5 min total)

### Static Analysis
- [x] ESLint: 0 errors
- [x] Ruff: 0 errors
- [x] MyPy: 0 type errors (--strict)
- [x] Prettier: all files formatted
- [x] Bandit: 0 high/medium security issues

### Documentation
- [x] Code is self-documenting (good names)
- [x] Public APIs have docstrings
- [x] Architecture docs updated if structure changed
- [x] No obsolete comments

### Functional
- [x] Application runs without errors
- [x] E2E tests pass
- [x] No regressions in user-facing behavior
- [x] Performance not degraded

---

## 📝 FINAL CHECKLIST

**Before declaring refactoring complete**:

### Pre-Merge Validation
- [ ] All tests pass (`npm test && pytest`)
- [ ] All linters pass (`npm run lint && ruff check src/`)
- [ ] Type checking passes (`mypy src/ --strict`)
- [ ] Build succeeds (`npm run build`)
- [ ] Coverage reports generated and ≥80%
- [ ] E2E tests pass (`npm run test:e2e && pytest tests/e2e/`)

### Documentation
- [ ] Refactoring report completed
- [ ] Metrics comparison documented
- [ ] Remaining technical debt documented
- [ ] Git commits are atomic and well-described

### User Communication
- [ ] Final report shared with user
- [ ] Remaining issues highlighted
- [ ] Next steps proposed
- [ ] User approval obtained for merge

### Git Hygiene
- [ ] All changes committed
- [ ] Commit messages follow Conventional Commits
- [ ] No merge conflicts with main
- [ ] Branch ready for code review

---

## 🎓 REFACTORING PRINCIPLES TO REMEMBER

### The Boy Scout Rule
> "Leave the code better than you found it."

Every file you touch should be cleaner after refactoring.

### Red-Green-Refactor
> "Make it work, make it right, make it fast."

1. **Red**: Write failing test
2. **Green**: Make it pass (quick & dirty OK)
3. **Refactor**: Clean up while keeping tests green

### YAGNI (You Aren't Gonna Need It)
> "Don't add functionality until necessary."

Remove speculative code. Simplify over-engineered solutions.

### KISS (Keep It Simple, Stupid)
> "Simplicity is the ultimate sophistication."

Simple code is:
- Easier to understand
- Easier to test
- Easier to maintain
- Harder to break

### Refactor Relentlessly
> "Code is read 10x more than written."

Optimize for readability, not cleverness.

### No Compromise on Quality
> "Quality is not negotiable."

- Hard to test? Refactor until testable.
- Big refactoring needed? Do it systematically.
- Complex code? Simplify it, no matter how long it takes.
- User expects excellence, not excuses.

**Agent convenience < Code quality. ALWAYS.**

---

## 🔗 RELATED DOCUMENTS

- **AGENTS.md** - General agent rules, TDD requirements, commit guidelines
- **CONTRIBUTING.md** - Development workflow
- **backend/bose_api/README.md** - Bose API reference
- **docs/ARCHITECTURE.md** - System architecture (update if you change it!)

---

**REMEMBER**:
- 🧪 Tests must ALWAYS be green
- 📖 Read code line-by-line before refactoring
- 🔄 Small steps with continuous validation
- 📝 Atomic commits with clear messages
- 🚫 NO experiments without user approval
- 👤 USER AUTHORITY - User has final say on all decisions

**BEGIN WITH PHASE 0 - DEEP CONTEXT ACQUISITION**

**DO NOT SKIP THE LINE-BY-LINE CODE READING!**
