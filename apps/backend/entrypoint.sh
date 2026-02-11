#!/bin/sh
# Entrypoint script for OpenCloudTouch backend
# Handles pre-startup validation, graceful shutdown, and configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo "${RED}[ERROR]${NC} $1"
}

# Validate required environment variables
validate_env() {
    log_info "Validating environment variables..."

    # OCT_PORT must be numeric
    if ! echo "$OCT_PORT" | grep -qE '^[0-9]+$'; then
        log_error "OCT_PORT must be numeric (got: $OCT_PORT)"
        exit 1
    fi

    # OCT_LOG_LEVEL must be valid
    case "$OCT_LOG_LEVEL" in
        DEBUG|INFO|WARNING|ERROR|CRITICAL)
            log_info "Log level: $OCT_LOG_LEVEL"
            ;;
        *)
            log_error "OCT_LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL (got: $OCT_LOG_LEVEL)"
            exit 1
            ;;
    esac

    log_info "Environment validation passed"
}

# Ensure data directory exists and is writable
validate_data_dir() {
    log_info "Validating data directory: $OCT_DB_PATH"

    DB_DIR=$(dirname "$OCT_DB_PATH")

    if [ ! -d "$DB_DIR" ]; then
        log_error "Data directory does not exist: $DB_DIR"
        exit 1
    fi

    if [ ! -w "$DB_DIR" ]; then
        log_error "Data directory is not writable: $DB_DIR"
        exit 1
    fi

    log_info "Data directory OK"
}

# Database initialization check
check_database() {
    log_info "Checking database: $OCT_DB_PATH"

    if [ ! -f "$OCT_DB_PATH" ]; then
        log_info "Database does not exist - will be created on first startup"
    else
        log_info "Database exists (size: $(stat -c%s "$OCT_DB_PATH" 2>/dev/null || stat -f%z "$OCT_DB_PATH" 2>/dev/null || echo "unknown") bytes)"
    fi
}

# Health check helper (can be used in HEALTHCHECK commands)
health_check() {
    python -c "
import urllib.request
import sys
try:
    urllib.request.urlopen('http://localhost:${OCT_PORT}/health', timeout=5)
    sys.exit(0)
except Exception as e:
    print(f'Health check failed: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# Graceful shutdown handler
shutdown() {
    log_warn "Received shutdown signal, terminating gracefully..."
    # Forward signal to Python process
    kill -TERM "$PID" 2>/dev/null || true
    wait "$PID"
    log_info "Shutdown complete"
    exit 0
}

# Main entrypoint logic
main() {
    log_info "OpenCloudTouch starting..."
    log_info "Version: 0.2.0"
    log_info "Python: $(python --version)"

    # Run validations
    validate_env
    validate_data_dir
    check_database

    # Handle special commands
    case "${1:-}" in
        health)
            health_check
            exit $?
            ;;
        version)
            python -c "import opencloudtouch; print(opencloudtouch.__version__ if hasattr(opencloudtouch, '__version__') else '0.2.0')"
            exit 0
            ;;
        shell)
            log_info "Starting interactive shell..."
            exec /bin/sh
            ;;
    esac

    # Setup signal handlers for graceful shutdown
    trap shutdown SIGTERM SIGINT

    log_info "Starting application on ${OCT_HOST}:${OCT_PORT}"
    log_info "Database: $OCT_DB_PATH"
    log_info "Discovery: ${OCT_DISCOVERY_ENABLED:-true}"

    # Start application in background to handle signals
    python -m opencloudtouch &
    PID=$!

    # Wait for process to complete
    wait "$PID"
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        log_error "Application exited with code $EXIT_CODE"
        exit $EXIT_CODE
    fi

    log_info "Application stopped normally"
}

# Run main function
main "$@"
