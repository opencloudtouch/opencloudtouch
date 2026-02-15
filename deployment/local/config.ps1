# Common configuration loader for deployment scripts
# Sources .env file if it exists, otherwise uses defaults

function Load-DeploymentConfig {
    $envFile = Join-Path $PSScriptRoot ".env"

    # Default values
    $config = @{
        DEPLOY_HOST = "localhost"
        DEPLOY_USER = $env:USERNAME
        DEPLOY_USE_SUDO = $false
        CONTAINER_NAME = "opencloudtouch"
        CONTAINER_TAG = "opencloudtouch:latest"
        REMOTE_DATA_PATH = "/data/opencloudtouch"
        REMOTE_IMAGE_PATH = "/tmp"
        LOCAL_DATA_PATH = Join-Path $PSScriptRoot "..\data-local"
        CONTAINER_PORT = 7777
        OCT_MANUAL_DEVICE_IPS = ""
        OCT_STATION_DESCRIPTOR_BASE_URL = ""
    }

    # Load .env if exists
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object {
            $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$'
        } | ForEach-Object {
            if ($_ -match '^([^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim()
                if ($config.ContainsKey($key)) {
                    $config[$key] = $value
                }
            }
        }
    }

    return $config
}
