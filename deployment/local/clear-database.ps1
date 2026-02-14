#!/usr/bin/env pwsh
# Clear the OpenCloudTouch database on remote server

param(
    [string]$RemoteHost = "",
    [string]$RemoteUser = "",
    [string]$DataPath = "",
    [string]$ContainerName = ""
)

# Load configuration from .env
. "$PSScriptRoot\config.ps1"
$config = Load-DeploymentConfig

if (-not $TrueNasHost) { $TrueNasHost = $config.DEPLOY_HOST }
if (-not $TrueNasUser) { $TrueNasUser = $config.DEPLOY_USER }
if (-not $DataPath) { $DataPath = $config.REMOTE_DATA_PATH }
if (-not $ContainerName) { $ContainerName = $config.CONTAINER_NAME }

Write-Host ""
Write-Host "=== Clear OpenCloudTouch Database ===" -ForegroundColor Yellow
Write-Host ""
Write-Host "Target: $TrueNasUser@$TrueNasHost" -ForegroundColor White
Write-Host "Database: $DataPath/oct.db" -ForegroundColor White
Write-Host ""

$confirmation = Read-Host "Are you sure you want to delete the database? (yes/no)"

if ($confirmation -ne "yes") {
    Write-Host "Cancelled." -ForegroundColor Gray
    exit 0
}

Write-Host "[>] Clearing database..." -ForegroundColor Cyan

$clearScript = @"
#!/bin/bash
set -e
DataPath="$DataPath"
ContainerName="$ContainerName"

if [ -f "\${DataPath}/oct.db" ]; then
    rm -f "\${DataPath}/oct.db"
    echo "[OK] Database deleted: \${DataPath}/oct.db"
else
    echo "[INFO] Database not found (already empty)"
fi

echo "[>] Restarting container..."
docker restart "`${ContainerName}"
echo "[OK] Container restarted: `${ContainerName}"
"@

$clearScript = $clearScript -replace "`r`n", "`n"
$clearScript | ssh "${RemoteUser}@${RemoteHost}" "bash -s"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Database cleared and container restarted!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Access the app at: http://${RemoteHost}:7777" -ForegroundColor Cyan
    Write-Host "You should now see the empty state with 'Keine Geräte gefunden'" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[ERROR] Failed to clear database or restart container" -ForegroundColor Red
    exit 1
}
