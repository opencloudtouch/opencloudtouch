#!/usr/bin/env pwsh
# Deploy OpenCloudTouch to remote server via SSH
# Builds locally, transfers image, and deploys remotely

param(
    [string]$ManualIPs = "",  # Comma-separated list of IPs (e.g., "192.168.1.10,192.168.1.11")
    [switch]$SkipBuild,
    [switch]$NoCache,
    [switch]$UseSudo,
    [switch]$ClearDatabase = $true,
    [switch]$Verbose
)

# Load configuration from .env
. "$PSScriptRoot\config.ps1"
$config = Load-DeploymentConfig

$RemoteHost = $config.DEPLOY_HOST
$RemoteUser = $config.DEPLOY_USER
$Tag = $config.CONTAINER_TAG
$ContainerName = $config.CONTAINER_NAME
$DataPath = $config.REMOTE_DATA_PATH
if (-not $ManualIPs -and $config.MANUAL_DEVICE_IPS) {
    $ManualIPs = $config.MANUAL_DEVICE_IPS
}
if ($config.DEPLOY_USE_SUDO -eq "true") {
    $UseSudo = $true
}

function Write-Step {
    param([string]$Message)
    Write-Host "[>] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

try {
    Write-Host ""
    Write-Host "=== Deploy OpenCloudTouch to Remote Server ===" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Target: $RemoteUser@$RemoteHost" -ForegroundColor White
    Write-Host ""

    $imageTar = "opencloudtouch-image.tar"

    # Step 1: Build and export locally
    Write-Step "Building and exporting image..."
    $exportArgs = @()
    if ($NoCache) { $exportArgs += "-NoCache" }
    if ($Verbose) { $exportArgs += "-Verbose" }
    & "$PSScriptRoot\export-image.ps1" @exportArgs
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Export failed!"
        exit 1
    }

    # Step 2: Transfer to remote server
    Write-Step "Transferring image to remote server..."
    scp $imageTar "${RemoteUser}@${RemoteHost}:/tmp/"
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Transfer failed! Check SSH connection."
        exit 1
    }
    Write-Success "Image transferred"

    # Step 3: Deploy on remote server
    Write-Step "Deploying container on remote server..."

    # Determine if sudo is needed
    $dockerCmd = if ($UseSudo) { "sudo docker" } else { "docker" }

    # Build docker run command
    $runCmd = "$dockerCmd run -d --name $ContainerName --restart unless-stopped --network host -v ${DataPath}:/data -e CT_LOG_LEVEL=DEBUG -e CT_DISCOVERY_ENABLED=true"

    if ($ManualIPs) {
        $runCmd += " -e CT_MANUAL_DEVICE_IPS='$ManualIPs'"
        Write-Host "    Using manual device IPs + SSDP discovery: $ManualIPs" -ForegroundColor Gray
    } else {
        Write-Host "    SSDP/mDNS discovery enabled" -ForegroundColor Gray
    }

    $runCmd += " $Tag"

    # Remote deployment script
    $deployScript = @"
#!/bin/bash
set -e
ClearDatabase=$ClearDatabase

echo "[>] Checking Docker access..."
if ! $dockerCmd version &>/dev/null; then
    echo "[ERROR] Cannot access Docker. You may need to:"
    echo "  1. Add user to docker group: sudo usermod -aG docker \`$USER"
    echo "  2. Or use -UseSudo flag if you have sudo rights"
    exit 1
fi

echo "[>] Loading Docker image..."
$dockerCmd load -i /tmp/$imageTar

echo "[>] Retagging image (removing localhost prefix)..."
$dockerCmd tag localhost/$Tag $Tag 2>/dev/null || true

echo "[>] Stopping existing container (if any)..."
$dockerCmd stop $ContainerName 2>/dev/null || true
$dockerCmd rm $ContainerName 2>/dev/null || true

echo "[>] Creating data directory..."
mkdir -p $DataPath 2>/dev/null || sudo mkdir -p $DataPath

if [ "\$ClearDatabase" = "True" ]; then
    echo "[>] Clearing database..."
    rm -f $DataPath/ct.db 2>/dev/null || sudo rm -f $DataPath/ct.db
    echo "[OK] Database cleared"
fi

echo "[>] Starting container..."
$runCmd

echo "[OK] Container started successfully"
$dockerCmd ps --filter name=$ContainerName --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "Access SoundTouch Bridge at: http://${RemoteHost}:7777"
echo ""
echo "View logs: $dockerCmd logs -f $ContainerName"
"@

    # Execute deployment - convert to Unix line endings
    $deployScript = $deployScript -replace "`r`n", "`n"
    $deployScript | ssh "${RemoteUser}@${RemoteHost}" "bash -s"

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "Deployment complete!"
        Write-Host ""
        Write-Host "=== Container Info ===" -ForegroundColor Yellow
        Write-Host "URL: http://${RemoteHost}:7777" -ForegroundColor Green

        $logsCmd = if ($UseSudo) { "sudo docker" } else { "docker" }
        Write-Host "Logs: ssh ${RemoteUser}@${RemoteHost} '$logsCmd logs -f $ContainerName'" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-ErrorMsg "Deployment failed! Check logs above."
        Write-Host ""
        Write-Host "Common issues:" -ForegroundColor Yellow
        Write-Host "- User not in docker group: ssh ${RemoteUser}@${RemoteHost} 'sudo usermod -aG docker ${RemoteUser}'" -ForegroundColor Gray
        Write-Host "- Or try with sudo: .\deploy-to-server.ps1 -UseSudo" -ForegroundColor Gray
        Write-Host ""
    }

} catch {
    Write-ErrorMsg "Deployment failed: $_"
    exit 1
} finally {
    # Cleanup local tar file
    if (Test-Path $imageTar) {
        Remove-Item $imageTar -Force
        Write-Host "Cleaned up local image file" -ForegroundColor Gray
    }
}
