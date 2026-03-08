#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Configure SoundTouch device to use custom streaming server port via envswitch.

.DESCRIPTION
    Connects to SoundTouch device service port 17000 and sends envswitch command
    to configure streaming URLs with custom port.

.PARAMETER DeviceIP
    IP address of the SoundTouch device (default: 192.168.1.79)

.PARAMETER StreamingURL
    Base URL for streaming service (default: http://streaming.bose.com:7777)

.EXAMPLE
    .\configure-device-port.ps1 -DeviceIP 192.168.1.79 -StreamingURL "http://streaming.bose.com:7777"
#>

param(
    [string]$DeviceIP = "192.168.1.79",
    [string]$StreamingURL = "http://streaming.bose.com:7777"
)

$UpdatesURL = "${StreamingURL}/updates/soundtouch"

Write-Host "=== SoundTouch Device Port Configuration ===" -ForegroundColor Yellow
Write-Host "Device IP: $DeviceIP" -ForegroundColor Cyan
Write-Host "Streaming URL: $StreamingURL" -ForegroundColor Cyan
Write-Host "Updates URL: $UpdatesURL" -ForegroundColor Cyan
Write-Host ""

# Create command sequence
$commands = @(
    "envswitch boseurls set $StreamingURL $UpdatesURL"
    "exit"
)

Write-Host "[>] Connecting to device service port 17000..." -ForegroundColor Cyan

try {
    # Use here-string to pipe commands with proper line endings
    $cmdString = ($commands -join "`n") + "`n"

    $sshCmd = "ssh -oHostKeyAlgorithms=ssh-rsa -oPubkeyAcceptedKeyTypes=ssh-rsa -oKexAlgorithms=diffie-hellman-group1-sha1 -oCiphers=aes128-cbc root@$DeviceIP"

    # Execute with timeout
    $process = Start-Process -FilePath "powershell" -ArgumentList "-Command", "echo '$cmdString' | $sshCmd 'nc localhost 17000'" -NoNewWindow -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "[OK] Configuration sent successfully" -ForegroundColor Green
        Write-Host ""
        Write-Host "⚠️  IMPORTANT: Reboot device to apply changes!" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To reboot device:" -ForegroundColor Cyan
        Write-Host "  Invoke-WebRequest -Uri 'http://${DeviceIP}:8090/key' -Method POST -Body '<key state=`"press`" sender=`"Gabbo`">POWER</key>' -ContentType 'application/xml' -UseBasicParsing" -ForegroundColor Gray
    } else {
        Write-Host "[ERROR] Configuration failed (exit code: $($process.ExitCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] Failed to configure device: $_" -ForegroundColor Red
    exit 1
}
