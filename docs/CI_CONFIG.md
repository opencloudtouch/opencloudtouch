# CI/CD Configuration

This file contains centralized configuration for CI/CD pipelines, GitHub workflows, and pre-commit hooks.

## Coverage Thresholds

Both backend and frontend enforce **80% minimum coverage**:

### Backend
- **Threshold**: 80%
- **Command**: `pytest --cov=opencloudtouch --cov-report=xml --cov-report=term-missing --cov-fail-under=80`
- **Configuration**: `backend/pytest.ini`

### Frontend
- **Threshold**: 80% (lines, functions, branches, statements)
- **Command**: `npm run test:coverage`
- **Configuration**: `frontend/vitest.config.js`

## Test Commands

### Backend Tests
- **Unit Tests**: `pytest tests/unit`
- **Integration Tests**: `pytest tests/integration`
- **All Tests**: `pytest` (includes unit + integration, excludes real device tests by default)

### Frontend Tests
- **Unit Tests**: `npm run test` or `npm run test:coverage`
- **E2E Tests (Cypress)**: `npm run test:e2e` (mock mode) or `npm run test:e2e:debug` (headed mode)

## Versions

- **Python**: 3.13
- **Node.js**: 20

## Where This Config Is Used

1. **GitHub Workflow** (`.github/workflows/ci-cd.yml`)
   - Backend tests with 80% coverage
   - Frontend unit tests with 80% coverage
   - Frontend E2E tests (Cypress)
   - Linting (ruff, black, mypy)

2. **Pre-commit Hook** (`pre-commit.ps1`)
   - Backend tests with 80% coverage
   - Frontend unit tests with 80% coverage
   - Frontend E2E tests

3. **Local Development**
   - Backend: `backend/pytest.ini`
   - Frontend: `frontend/vitest.config.js`

## Updating Coverage Thresholds

To change coverage thresholds, update these files:

1. **This file** (`.ci-config.json`) - documentation
2. **Backend**:
   - `backend/pytest.ini` (comment)
   - `.github/workflows/ci-cd.yml` (`--cov-fail-under=XX`)
3. **Frontend**:
   - `frontend/vitest.config.js` (`thresholds` object)
4. **Pre-commit Hook**:
   - `pre-commit.ps1` (comments + commands)

⚠️ **Important**: Keep all values synchronized at 80% unless there's a specific reason to diverge.
