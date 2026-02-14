#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Real Device Tests (ALL test suites against actual hardware)

.DESCRIPTION
    Runs tests against REAL Bose SoundTouch devices:
    1. Backend Real Device Tests (pytest tests/real)
    2. Frontend Real Device Tests (vitest tests/real)
    3. E2E Real Device Tests (Cypress tests/real)

    ⚠️  REQUIRES: Actual Bose SoundTouch devices on network!

    These tests are NOT run in CI/CD or pre-commit hooks.
    They must be run manually when hardware is available.

.PARAMETER SkipBackend
    Skip backend real device tests (default: false)

.PARAMETER SkipFrontend
    Skip frontend real device tests (default: false)

.PARAMETER SkipE2E
    Skip E2E real device tests (default: false)

.PARAMETER HeadlessMode
    Run Cypress headless (true) or with GUI (false). Default: true

.EXAMPLE
    .\scripts\run-real-tests.ps1
    .\scripts\run-real-tests.ps1 -HeadlessMode $false
    .\scripts\run-real-tests.ps1 -SkipBackend $true
#>

param(
    [bool]$SkipBackend = $false,
    [bool]$SkipFrontend = $false,
    [bool]$SkipE2E = $false,
    [bool]$HeadlessMode = $true
)

$ErrorActionPreference = "Stop"

# Fix console encoding for emojis
chcp 65001 >$null 2>&1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendDir = Join-Path $RootDir "apps\backend"
$FrontendDir = Join-Path $RootDir "apps\frontend"
$VenvPython = Join-Path (Join-Path $RootDir ".venv") "Scripts\python.exe"

# Colors
function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Write-Error($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Warning($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Section($msg) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host $msg -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host ""
}

$results = @{
    Backend = $null
    Frontend = $null
    E2E = $null
}

Write-Section "CloudTouch - Real Device Test Suite"
Write-Warning "⚠️  REQUIRES: Actual Bose SoundTouch devices on network!"
Write-Host ""
Write-Info "Make sure devices are:"
Write-Host "  - Powered ON" -ForegroundColor Yellow
Write-Host "  - Connected to same network" -ForegroundColor Yellow
Write-Host "  - Reachable from this machine" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to cancel, or wait 5 seconds to continue..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Set environment variable for real device tests
$env:CT_HAS_DEVICES = "true"

# 1. Backend Real Device Tests
if (-not $SkipBackend) {
    Write-Section "1/3: Backend Real Device Tests (pytest tests/real)"
    try {
        Set-Location $BackendDir

        # Run only tests/real directory with real_devices marker
        & $VenvPython -m pytest tests/real -v -m real_devices

        if ($LASTEXITCODE -eq 0) {
            $results.Backend = "PASSED"
        }
        else {
            $results.Backend = "FAILED"
        }
    }
    catch {
        Write-Error "Backend real device tests crashed: $_"
        $results.Backend = "CRASHED"
    }
    finally {
        Set-Location $RootDir
    }
}
else {
    Write-Info "Skipping backend real device tests"
    $results.Backend = "SKIPPED"
}

# 2. Frontend Real Device Tests
if (-not $SkipFrontend) {
    Write-Section "2/3: Frontend Real Device Tests (vitest tests/real)"
    try {
        Set-Location $FrontendDir

        # Run vitest with real device tests
        $env:CT_HAS_DEVICES = "true"
        $process = Start-Process -FilePath "npm" -ArgumentList "run", "test:real" -Wait -NoNewWindow -PassThru

        if ($process.ExitCode -eq 0) {
            $results.Frontend = "PASSED"
        }
        else {
            $results.Frontend = "FAILED"
        }
    }
    catch {
        Write-Error "Frontend real device tests crashed: $_"
        $results.Frontend = "CRASHED"
    }
    finally {
        Set-Location $RootDir
    }
}
else {
    Write-Info "Skipping frontend real device tests"
    $results.Frontend = "SKIPPED"
}

# 3. E2E Real Device Tests
if (-not $SkipE2E) {
    Write-Section "3/3: E2E Real Device Tests (Cypress tests/real)"
    try {
        Set-Location $FrontendDir

        # Run E2E tests in REAL mode (CT_MOCK_MODE=false)
        if ($HeadlessMode) {
            $process = Start-Process -FilePath "npm" -ArgumentList "run", "test:e2e:real" -Wait -NoNewWindow -PassThru
        }
        else {
            $process = Start-Process -FilePath "npm" -ArgumentList "run", "test:e2e:real:debug" -Wait -NoNewWindow -PassThru
        }

        if ($process.ExitCode -eq 0) {
            $results.E2E = "PASSED"
        }
        else {
            $results.E2E = "FAILED"
        }
    }
    catch {
        Write-Error "E2E real device tests crashed: $_"
        $results.E2E = "CRASHED"
    }
    finally {
        Set-Location $RootDir
    }
}
else {
    Write-Info "Skipping E2E real device tests"
    $results.E2E = "SKIPPED"
}

# Clean up environment
Remove-Item Env:\CT_HAS_DEVICES -ErrorAction SilentlyContinue

# Final Summary
Write-Section "REAL DEVICE TEST SUMMARY"
Write-Host "Backend Tests:  " -NoNewline
switch ($results.Backend) {
    "PASSED" { Write-Host "✅ PASSED" -ForegroundColor Green }
    "FAILED" { Write-Host "❌ FAILED" -ForegroundColor Red }
    "CRASHED" { Write-Host "💥 CRASHED" -ForegroundColor Red }
    "SKIPPED" { Write-Host "⏭️  SKIPPED" -ForegroundColor Yellow }
}

Write-Host "Frontend Tests: " -NoNewline
switch ($results.Frontend) {
    "PASSED" { Write-Host "✅ PASSED" -ForegroundColor Green }
    "FAILED" { Write-Host "❌ FAILED" -ForegroundColor Red }
    "CRASHED" { Write-Host "💥 CRASHED" -ForegroundColor Red }
    "SKIPPED" { Write-Host "⏭️  SKIPPED" -ForegroundColor Yellow }
}

Write-Host "E2E Tests:      " -NoNewline
switch ($results.E2E) {
    "PASSED" { Write-Host "✅ PASSED" -ForegroundColor Green }
    "FAILED" { Write-Host "❌ FAILED" -ForegroundColor Red }
    "CRASHED" { Write-Host "💥 CRASHED" -ForegroundColor Red }
    "SKIPPED" { Write-Host "⏭️  SKIPPED" -ForegroundColor Yellow }
}

Write-Host ""

# Exit code
$allPassed = ($results.Backend -in @("PASSED", "SKIPPED")) -and
             ($results.Frontend -in @("PASSED", "SKIPPED")) -and
             ($results.E2E -in @("PASSED", "SKIPPED"))

if ($allPassed) {
    Write-Success "All real device tests passed! 🎉"
    Write-Host ""
    Write-Info "Hardware validation complete - devices are working correctly."
    exit 0
}
else {
    Write-Error "Some real device tests failed!"
    Write-Host ""
    Write-Warning "Check device connectivity and network settings."
    exit 1
}
