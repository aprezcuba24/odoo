#!/bin/bash
# Build script for Seenode runtime deployment (non-Docker)
# Sets up system dependencies and installs Python packages.
set -e

echo "[BUILD] Installing system dependencies required by Odoo..."

apt-get update -qq && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    libxml2-dev \
    libxslt1-dev \
    libsass-dev \
    libldap2-dev \
    libsasl2-dev \
    fontconfig \
    xfonts-75dpi \
    xfonts-base \
    libxrender1 \
    libxext6 \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf for PDF generation
echo "[BUILD] Installing wkhtmltopdf..."
apt-get update -qq && \
    (apt-get install -y --no-install-recommends wkhtmltopdf 2>/dev/null || \
     (curl -fsSL https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
          -o /tmp/wkhtmltopdf.deb && \
      dpkg -i /tmp/wkhtmltopdf.deb || apt-get install -yf --no-install-recommends && \
      rm -f /tmp/wkhtmltopdf.deb)) && \
    rm -rf /var/lib/apt/lists/*

echo "[BUILD] Upgrading pip, setuptools and wheel..."
pip install --upgrade pip setuptools wheel

echo "[BUILD] Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

echo "[BUILD] Installing Gunicorn with gevent support..."
pip install "gunicorn[gevent]"

echo "[BUILD] Making odoo-bin executable..."
chmod +x odoo-bin

echo "[BUILD] Build completed successfully."
