#!/usr/bin/env pwsh
# Run E2E Hardware Tests on remote server with real SoundTouch devices

param(
    [string]$RemoteHost = "",
    [string]$RemoteUser = "",
    [string]$LogLevel = "DEBUG",
    [switch]$SkipDiscovery,
    [switch]$SkipIntegration,
    [switch]$Coverage
)

# Load configuration from .env
. "$PSScriptRoot\config.ps1"
$config = Load-DeploymentConfig

if (-not $RemoteHost) { $RemoteHost = $config.DEPLOY_HOST }
if (-not $RemoteUser) { $RemoteUser = $config.DEPLOY_USER }

Write-Host ""
Write-Host "=== Run E2E Tests on Remote Server ===" -ForegroundColor Yellow
Write-Host ""
Write-Host "Target: $RemoteUser@$RemoteHost" -ForegroundColor White
Write-Host "Log Level: $LogLevel" -ForegroundColor Gray
Write-Host ""

# Build test command
$testCmd = @"
#!/bin/bash
set -e

echo "[>] Checking Docker container..."
if ! docker ps --filter name=cloudtouch --format '{{.Names}}' | grep -q cloudtouch; then
    echo "[ERROR] CloudTouch container not running!"
    echo "Start it first: docker start cloudtouch"
    exit 1
fi

echo "[>] Checking Python installation..."
if ! command -v python3.11 &> /dev/null; then
    echo "[ERROR] Python 3.11 not found!"
    echo "Install: sudo apt install python3.11 python3.11-venv"
    exit 1
fi

echo "[>] Cloning/updating repository..."
cd /tmp
if [ -d "soundtouch-bridge-test" ]; then
    cd soundtouch-bridge-test
    git pull
else
    git clone https://github.com/<owner>/soundtouch-bridge.git soundtouch-bridge-test
    cd soundtouch-bridge-test
fi

echo "[>] Setting up Python environment..."
cd apps/backend
python3.11 -m venv .venv-test
source .venv-test/bin/activate
pip install -q -r requirements.txt -r requirements-dev.txt

echo ""
echo "=== Running Tests ==="
echo ""

export CT_HAS_DEVICES=true
export CT_LOG_LEVEL=$LogLevel
export PYTHONPATH=\$PWD/src

testsFailed=0

"@

if (-not $SkipDiscovery) {
    $testCmd += @"

echo "[>] Running E2E Discovery Tests..."
echo ""
if pytest tests/e2e/test_discovery_e2e.py -v --tb=short; then
    echo ""
    echo "[OK] E2E Discovery Tests PASSED"
else
    echo ""
    echo "[ERROR] E2E Discovery Tests FAILED"
    testsFailed=1
fi

"@
}

if (-not $SkipIntegration) {
    $testCmd += @"

echo ""
echo "[>] Running Real Integration Tests..."
echo ""
if pytest tests/integration/test_real_api_stack.py -v --tb=short; then
    echo ""
    echo "[OK] Real Integration Tests PASSED"
else
    echo ""
    echo "[ERROR] Real Integration Tests FAILED"
    testsFailed=1
fi

"@
}

if ($Coverage) {
    $testCmd += @"

echo ""
echo "[>] Running Full Test Suite with Coverage..."
echo ""
pytest tests/ --cov=cloudtouch --cov-report=term-missing --cov-fail-under=80

"@
}

$testCmd += @"

echo ""
echo "=== Test Summary ==="
echo ""
if [ \$testsFailed -eq 0 ]; then
    echo "[OK] All tests PASSED"
    exit 0
else
    echo "[ERROR] Some tests FAILED"
    exit 1
fi
"@

# Execute on remote server
try {
    Write-Host "[>] Connecting to remote server..." -ForegroundColor Cyan

    # Convert to Unix line endings
    $testCmd = $testCmd -replace "`r`n", "`n"

    # Replace placeholders
    $testCmd = $testCmd -replace "\`$LogLevel", $LogLevel

    # Execute via SSH
    $testCmd | ssh "${RemoteUser}@${RemoteHost}" "bash -s"

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[SUCCESS] E2E Tests completed!" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[FAILURE] E2E Tests failed!" -ForegroundColor Red
        Write-Host ""
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] SSH connection failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "- SSH not configured: ssh ${RemoteUser}@${RemoteHost}" -ForegroundColor Gray
    Write-Host "- Container not running: ssh ${RemoteUser}@${RemoteHost} 'docker start cloudtouch'" -ForegroundColor Gray
    exit 1
}
