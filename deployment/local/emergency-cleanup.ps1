#!/usr/bin/env pwsh
# Emergency cleanup script for stuck deployments

Write-Host "=== Emergency Cleanup ===" -ForegroundColor Yellow

# Stop and remove container
Write-Host "Stopping container..." -ForegroundColor Cyan
podman stop opencloudtouch-local 2>&1 | Out-Null
podman rm opencloudtouch-local 2>&1 | Out-Null

# Show logs if container exists
$logs = podman logs opencloudtouch-local 2>&1
if ($logs -and $logs.Length -gt 0) {
    Write-Host ""
    Write-Host "Last container logs:" -ForegroundColor Yellow
    $logs | Select-Object -Last 100
}

Write-Host ""
Write-Host "Cleanup complete!" -ForegroundColor Green
