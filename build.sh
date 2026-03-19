#!/bin/bash
# Build script for Seenode runtime deployment (non-Docker).
# Installs system libraries when possible, then Python dependencies.
#
# IMPORTANT: select Python 3.12 as the runtime in Seenode settings.
# Python 3.14 is pre-release and not supported by Odoo's dependencies.
set -e

# ---------------------------------------------------------------------------
# 1. System dependencies
#    Required for packages that compile C extensions: psycopg2, lxml, libsass,
#    python-ldap, Pillow, gevent…
#    We try as root, then with sudo, then fall back to binary-only pip mode.
# ---------------------------------------------------------------------------
SYS_PACKAGES="
    build-essential
    python3-dev
    libpq-dev
    libjpeg-dev
    zlib1g-dev
    libfreetype6-dev
    liblcms2-dev
    libwebp-dev
    libharfbuzz-dev
    libfribidi-dev
    libxcb1-dev
    libxml2-dev
    libxslt1-dev
    libsass-dev
    libldap2-dev
    libsasl2-dev
    fontconfig
    libxrender1
    libxext6
    curl
"

install_sys_deps() {
    # shellcheck disable=SC2086
    if [ "$(id -u)" = "0" ]; then
        echo "[BUILD] Running as root — using apt-get directly."
        apt-get update -qq
        # shellcheck disable=SC2086
        apt-get install -y --no-install-recommends $SYS_PACKAGES
        rm -rf /var/lib/apt/lists/*
    elif command -v sudo &>/dev/null; then
        echo "[BUILD] Running as non-root — using sudo apt-get."
        sudo apt-get update -qq
        # shellcheck disable=SC2086
        sudo apt-get install -y --no-install-recommends $SYS_PACKAGES
        sudo rm -rf /var/lib/apt/lists/*
    else
        echo "[BUILD] WARNING: No root or sudo available. Skipping system packages."
        return 1
    fi
}

SYSTEM_DEPS_OK=false
if install_sys_deps 2>&1; then
    echo "[BUILD] System dependencies installed successfully."
    SYSTEM_DEPS_OK=true
else
    echo "[BUILD] Could not install system packages — will use binary wheels only."
fi

# ---------------------------------------------------------------------------
# 2. wkhtmltopdf (PDF generation) — best-effort, non-fatal
# ---------------------------------------------------------------------------
if [ "$SYSTEM_DEPS_OK" = "true" ]; then
    echo "[BUILD] Installing wkhtmltopdf..."
    (apt-get update -qq 2>/dev/null || sudo apt-get update -qq 2>/dev/null || true)
    (apt-get install -y --no-install-recommends wkhtmltopdf 2>/dev/null \
        || sudo apt-get install -y --no-install-recommends wkhtmltopdf 2>/dev/null \
        || echo "[BUILD] WARNING: wkhtmltopdf not installed (PDF export will be unavailable).") \
        || true
    (rm -rf /var/lib/apt/lists/* 2>/dev/null || sudo rm -rf /var/lib/apt/lists/* 2>/dev/null || true)
fi

# ---------------------------------------------------------------------------
# 3. Prepare pip requirements
#    When system libs are available, use requirements.txt as-is.
#    Without system libs, swap psycopg2 → psycopg2-binary (no libpq-dev needed)
#    and add --prefer-binary so pip picks wheels over source for everything else.
# ---------------------------------------------------------------------------
echo "[BUILD] Upgrading pip, setuptools and wheel..."
pip install --upgrade pip setuptools wheel

PIP_REQUIREMENTS="requirements.txt"
PIP_FLAGS="--prefer-binary"

if [ "$SYSTEM_DEPS_OK" = "false" ]; then
    echo "[BUILD] Creating binary-friendly requirements (psycopg2 → psycopg2-binary)..."
    # Replace all psycopg2==x.y.z lines with psycopg2-binary==x.y.z
    sed 's/^psycopg2==/psycopg2-binary==/g' requirements.txt > /tmp/requirements-paas.txt
    PIP_REQUIREMENTS="/tmp/requirements-paas.txt"
fi

echo "[BUILD] Installing Python dependencies from ${PIP_REQUIREMENTS}..."
pip install $PIP_FLAGS -r "$PIP_REQUIREMENTS"

# ---------------------------------------------------------------------------
# 4. Gunicorn with gevent support (WebSockets)
# ---------------------------------------------------------------------------
echo "[BUILD] Installing Gunicorn with gevent support..."
pip install $PIP_FLAGS "gunicorn[gevent]"

# ---------------------------------------------------------------------------
# 5. Housekeeping
# ---------------------------------------------------------------------------
echo "[BUILD] Making odoo-bin executable..."
chmod +x odoo-bin

echo ""
echo "[BUILD] ✓ Build completed successfully."
echo "[BUILD]   System deps: ${SYSTEM_DEPS_OK}"
echo "[BUILD]   Python: $(python3 --version)"
echo "[BUILD]   pip: $(pip --version)"
