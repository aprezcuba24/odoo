#!/bin/bash
# Script to start Odoo with Gunicorn
# This script can be used for manual startup or in production environments

set -e

# Configuration
PROJECT_DIR="/app"
CONFIG_FILE="${PROJECT_DIR}/gunicorn.conf.py"
PID_FILE="/var/run/odoo/gunicorn.pid"
LOG_DIR="/var/log/odoo"
RUN_DIR="/var/run/odoo"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root. Use a dedicated user (e.g., odoo)."
    exit 1
fi

# Create necessary directories
print_info "Creating necessary directories..."
sudo mkdir -p "${LOG_DIR}" "${RUN_DIR}"
sudo chown -R $(whoami):$(whoami) "${LOG_DIR}" "${RUN_DIR}" 2>/dev/null || \
    print_warn "Could not change ownership of directories. You may need to run: sudo chown -R $(whoami):$(whoami) ${LOG_DIR} ${RUN_DIR}"

# Check if Gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    print_error "Gunicorn is not installed. Please install it first: pip install gunicorn"
    exit 1
fi

# Check if config file exists
if [ ! -f "${CONFIG_FILE}" ]; then
    print_error "Configuration file not found: ${CONFIG_FILE}"
    exit 1
fi

# Check if Odoo is already running
if [ -f "${PID_FILE}" ]; then
    if ps -p $(cat "${PID_FILE}") > /dev/null 2>&1; then
        print_warn "Odoo Gunicorn is already running (PID: $(cat ${PID_FILE}))"
        read -p "Do you want to restart it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Stopping existing instance..."
            kill -HUP $(cat "${PID_FILE}")
            sleep 2
        else
            exit 0
        fi
    else
        print_warn "Stale PID file found. Removing..."
        rm -f "${PID_FILE}"
    fi
fi

# Start Gunicorn
print_info "Starting Odoo with Gunicorn..."
cd "${PROJECT_DIR}"

exec gunicorn \
    odoo.http:root \
    --pythonpath "${PROJECT_DIR}" \
    --config "${CONFIG_FILE}" \
    --bind 127.0.0.1:8069 \
    --workers 4 \
    --timeout 240 \
    --max-requests 2000 \
    --pid "${PID_FILE}" \
    --access-logfile "${LOG_DIR}/gunicorn-access.log" \
    --error-logfile "${LOG_DIR}/gunicorn-error.log" \
    --log-level info \
    --capture-output

