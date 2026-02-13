# Test RFC 7807 Error Response Structure
$ErrorActionPreference = "Stop"

Write-Host "Starting backend..." -ForegroundColor Cyan
$env:OCT_MOCK_MODE = "true"
$env:OCT_DB_PATH = ":memory:"

$backend = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "opencloudtouch.main:app", "--host", "127.0.0.1", "--port", "7779" `
    -WorkingDirectory "apps\backend" `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 5

try {
    Write-Host "`n=== Testing ERROR_500 ===" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:7779/api/radio/search?q=ERROR_500&search_type=name&limit=10" `
        -Method GET -SkipHttpErrorCheck

    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Content-Type: $($response.Headers['Content-Type'])" -ForegroundColor Green
    Write-Host "`nResponse Body:" -ForegroundColor Cyan
    $json = $response.Content | ConvertFrom-Json
    $json | ConvertTo-Json -Depth 5

    Write-Host "`n=== Testing ERROR_503 ===" -ForegroundColor Yellow
    $response2 = Invoke-WebRequest -Uri "http://127.0.0.1:7779/api/radio/search?q=ERROR_503&search_type=name&limit=10" `
        -Method GET -SkipHttpErrorCheck

    Write-Host "Status Code: $($response2.StatusCode)" -ForegroundColor Green
    $json2 = $response2.Content | ConvertFrom-Json
    $json2 | ConvertTo-Json -Depth 5

    Write-Host "`n=== Testing ERROR_504 ===" -ForegroundColor Yellow
    $response3 = Invoke-WebRequest -Uri "http://127.0.0.1:7779/api/radio/search?q=ERROR_504&search_type=name&limit=10" `
        -Method GET -SkipHttpErrorCheck

    Write-Host "Status Code: $($response3.StatusCode)" -ForegroundColor Green
    $json3 = $response3.Content | ConvertFrom-Json
    $json3 | ConvertTo-Json -Depth 5

} finally {
    Write-Host "`nStopping backend..." -ForegroundColor Cyan
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}

Write-Host "`nDone!" -ForegroundColor Green
