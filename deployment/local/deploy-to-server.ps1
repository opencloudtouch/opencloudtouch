#!/usr/bin/env pwsh
# Deploy OpenCloudTouch to TrueNAS via SSH
# Builds locally, transfers image, and deploys remotely

param(
    [string]$ManualIPs = "",  # Comma-separated list of IPs (e.g., "192.168.1.10,192.168.1.11")
    [switch]$SkipBuild,
    [switch]$NoCache,
    [switch]$UseSudo,
    [switch]$ClearDatabase = $true,
    [switch]$Verbose
)

# Configuration - adjust these values if needed
$TrueNasHost = "targethost"
$TrueNasUser = "user"
$Tag = "opencloudtouch:latest"
$ContainerName = "opencloudtouch"
$DataPath = "/mnt/Docker/opencloudtouch/data"

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
    Write-Host "=== Deploy OpenCloudTouch to TrueNAS ===" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Target: $TrueNasUser@$TrueNasHost" -ForegroundColor White
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

    # Step 2: Transfer to TrueNAS
    Write-Step "Transferring image to TrueNAS..."
    scp $imageTar "${TrueNasUser}@${TrueNasHost}:/tmp/"
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Transfer failed! Check SSH connection."
        exit 1
    }
    Write-Success "Image transferred"

    # Step 3: Deploy on TrueNAS
    Write-Step "Deploying container on TrueNAS..."

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
echo "Access SoundTouch Bridge at: http://${TrueNasHost}:7777"
echo ""
echo "View logs: $dockerCmd logs -f $ContainerName"
"@

    # Execute deployment - convert to Unix line endings
    $deployScript = $deployScript -replace "`r`n", "`n"
    $deployScript | ssh "${TrueNasUser}@${TrueNasHost}" "bash -s"

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "Deployment complete!"
        Write-Host ""
        Write-Host "=== Container Info ===" -ForegroundColor Yellow
        Write-Host "URL: http://${TrueNasHost}:7777" -ForegroundColor Green

        $logsCmd = if ($UseSudo) { "sudo docker" } else { "docker" }
        Write-Host "Logs: ssh ${TrueNasUser}@${TrueNasHost} '$logsCmd logs -f $ContainerName'" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-ErrorMsg "Deployment failed! Check logs above."
        Write-Host ""
        Write-Host "Common issues:" -ForegroundColor Yellow
        Write-Host "- User not in docker group: ssh ${TrueNasUser}@${TrueNasHost} 'sudo usermod -aG docker ${TrueNasUser}'" -ForegroundColor Gray
        Write-Host "- Or try with sudo: .\deploy-to-server.ps1 -TrueNasHost $TrueNasHost -TrueNasUser $TrueNasUser -UseSudo" -ForegroundColor Gray
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
