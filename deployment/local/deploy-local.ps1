#!/usr/bin/env pwsh
# Deploy SoundTouch Bridge locally with Podman for development/testing
# Supports mock mode with fake devices for UI development

param(
    [switch]$NoCache,
    [switch]$Verbose,
    [switch]$SkipBuild,
    [string]$Port = "7777"
)

$ErrorActionPreference = "Stop"

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
    Write-Host "=== Deploy OpenCloudTouch Locally (Podman) ===" -ForegroundColor Yellow
    Write-Host ""

    # Step 0: Ensure Podman is ready
    Write-Step "Ensuring Podman is ready..."

    # Suppress all output/errors from Podman machine commands (they're noisy but harmless)
    try {
        podman machine stop *>&1 | Out-Null
        Start-Sleep -Seconds 2

        podman machine set --rootful *>&1 | Out-Null

        podman machine start *>&1 | Out-Null
        Start-Sleep -Seconds 3
    }
    catch {
        # Ignore - will verify with podman version below
    }

    # Verify Podman is actually accessible
    podman version *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Podman not accessible after restart!"
        Write-Host "Manual fix: podman machine stop && podman machine set --rootful && podman machine start" -ForegroundColor Yellow
        exit 1
    }

    Write-Success "Podman ready (rootful mode)"
    Write-Host ""

    $Tag = "opencloudtouch:latest"
    $ContainerName = "opencloudtouch-local"
    $LocalDataPath = "$PSScriptRoot\..\data-local"

    # Create local data directory
    if (-not (Test-Path $LocalDataPath)) {
        Write-Step "Creating local data directory..."
        New-Item -ItemType Directory -Path $LocalDataPath -Force | Out-Null
        Write-Success "Created $LocalDataPath"
    }

    # Step 1: Build image (unless skipped)
    if (-not $SkipBuild) {
        Write-Step "Building Docker image..."
        $buildArgs = @("build", "-t", $Tag)
        if ($NoCache) {
            $buildArgs += "--no-cache"
        }
        $buildArgs += "-f"
        $buildArgs += "Dockerfile"
        $buildArgs += "."

        if ($Verbose) {
            Write-Host "Command: podman $($buildArgs -join ' ')" -ForegroundColor DarkGray
        }

        $buildOutput = & podman @buildArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorMsg "Build failed!"
            Write-Host $buildOutput -ForegroundColor Red
            exit 1
        }
        Write-Success "Image built successfully"
    }
    else {
        Write-Step "Skipping build (using existing image)"
    }

    # Step 2: Stop and remove existing container
    Write-Step "Stopping existing container (if any)..."
    $existingContainer = podman ps -a --filter "name=$ContainerName" --format "{{.Names}}" 2>$null
    if ($existingContainer -eq $ContainerName) {
        podman stop $ContainerName 2>&1 | Out-Null
        podman rm $ContainerName 2>&1 | Out-Null
        Write-Success "Removed old container"
    }
    else {
        Write-Host "  No existing container found" -ForegroundColor DarkGray
    }

    # Step 3: Run container
    Write-Step "Starting container..."

    # Use --network host for SSDP multicast to work
    # (port mapping -p blocks multicast traffic)
    $runArgs = @(
        "run",
        "-d",
        "--name", $ContainerName,
        #"-p", "${Port}:${Port}",
        #"--network", "host",
        "--net", "host",
        "-v", "${LocalDataPath}:/data",
        "-e", "OCT_LOG_LEVEL=DEBUG",
        "-e", "OCT_DB_PATH=/data/oct.db",
        $Tag
    )

    if ($Verbose) {
        Write-Host "Command: podman $($runArgs -join ' ')" -ForegroundColor DarkGray
    }

    $containerId = & podman @runArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Failed to start container!"
        Write-Host $containerId -ForegroundColor Red
        exit 1
    }

    Write-Success "Container started: $ContainerName"
    Write-Host ""

    # Get WSL IP for Mirror Mode networking
    Write-Step "Detecting WSL IP address..."
    $wslIpRaw = wsl -d podman-machine-default -- ip -4 addr show |
        Select-String -Pattern "inet\s+(\d+\.\d+\.\d+\.\d+).*eth" |
        ForEach-Object { $_.Matches.Groups[1].Value } |
        Select-Object -First 1

    $wslIp = if ($wslIpRaw) { $wslIpRaw.Trim() } else { $null }

    if (-not $wslIp) {
        Write-ErrorMsg "Failed to detect WSL IP address"
        exit 1
    }
    Write-Host "  Using WSL IP: $wslIp" -ForegroundColor DarkGray
    Write-Host ""

    # Step 4: Wait for health check
    Write-Step "Waiting for service to be ready..."
    $maxRetries = 2
    $retryInterval = 5
    $retryCount = 0
    $healthOk = $false

    # Health check inside WSL (Mirror Mode blocks Windows->WSL localhost forwarding)
    $healthCmd = "curl -s -o /dev/null -w '%{http_code}' http://localhost:${Port}/health"

    while ($retryCount -lt $maxRetries) {
        $retryCount++
        Write-Host "  [DEBUG] Health check attempt $retryCount/$maxRetries..." -ForegroundColor DarkGray

        # Check if container is even running
        $containerState = podman inspect $ContainerName --format '{{.State.Status}}' 2>$null
        Write-Host "  [DEBUG] Container state: $containerState" -ForegroundColor DarkGray

        if ($containerState -ne "running") {
            Write-Host "  [DEBUG] Container not running! Checking logs..." -ForegroundColor Yellow
            wsl -d podman-machine-default -- podman logs $ContainerName --tail 30 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            Write-ErrorMsg "Container crashed immediately - see logs above"
            exit 1
        }

        Start-Sleep -Seconds $retryInterval
        try {
            $httpCode = wsl -d podman-machine-default bash -c $healthCmd 2>$null
            Write-Host "  [DEBUG] Health endpoint returned: $httpCode" -ForegroundColor DarkGray
            if ($httpCode -eq "200") {
                $healthOk = $true
                break
            }
        }
        catch {
            # Expected during startup
        }
        $retryCount++
        if ($retryCount -gt 5) {
            Write-Host "  Retry $retryCount/$maxRetries..." -ForegroundColor DarkGray
        }
    }

    Write-Host ""
    if ($healthOk) {
        Write-Success "Service is ready!"
        Write-Host ""
        Write-Host "=== CloudTouch Local Deployment ===" -ForegroundColor Green
        Write-Host ""
        Write-Host "  UI:         " -NoNewline; Write-Host "http://localhost:${Port}" -ForegroundColor Cyan
        Write-Host "  API:        " -NoNewline; Write-Host "http://localhost:${Port}/api/devices" -ForegroundColor Cyan
        Write-Host "  Health:     " -NoNewline; Write-Host "http://localhost:${Port}/health" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  Note: If localhost doesn't work, use WSL IP: http://${wslIp}:${Port}" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor White
        Write-Host "  View logs:  " -NoNewline; Write-Host "podman logs $ContainerName -f" -ForegroundColor Cyan
        Write-Host "  Stop:       " -NoNewline; Write-Host "podman stop $ContainerName" -ForegroundColor Cyan
        Write-Host "  Restart:    " -NoNewline; Write-Host "podman restart $ContainerName" -ForegroundColor Cyan
        Write-Host "  Remove:     " -NoNewline; Write-Host "podman rm -f $ContainerName" -ForegroundColor Cyan
        Write-Host ""

        exit 0
    }
    else {
        Write-ErrorMsg "Service did not become ready in time (waited $maxRetries seconds)"
        Write-Host ""
        Write-Host "Container status:" -ForegroundColor Yellow
        podman ps -a --filter "name=$ContainerName" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        Write-Host ""
        Write-Host "Last 50 log lines:" -ForegroundColor Yellow
        podman logs $ContainerName 2>&1 | Select-Object -Last 50
        exit 1
    }
}
catch {
    Write-ErrorMsg "Deployment failed: $_"
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
