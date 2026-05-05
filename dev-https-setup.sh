#!/usr/bin/env bash
# dev-https-setup.sh — One-time helper for HTTPS in local development.
#
# Copies Caddy's auto-generated root CA to /tmp so you can trust it in
# your browser/OS once, then updates web.base.url in the target Odoo DB.
#
# Usage (inside the devcontainer):
#   bash dev-https-setup.sh [DATABASE_NAME]
#
# DATABASE_NAME defaults to "odoo1".

set -euo pipefail

DB="${1:-odoo1}"
BASE_URL="https://localhost"

# ── 1. Export Caddy's root CA ──────────────────────────────────────────────
CA_DEST="/tmp/caddy-root.crt"
CA_SRC="/data/caddy/pki/authorities/local/root.crt"

echo "Copying Caddy root CA from the caddy container..."
docker cp odoo-caddy:"${CA_SRC}" "${CA_DEST}" 2>/dev/null || {
    echo ""
    echo "Could not copy the CA cert automatically (is the 'odoo-caddy' container running?)."
    echo "Run this yourself once the container is up:"
    echo "  docker cp odoo-caddy:${CA_SRC} ${CA_DEST}"
    echo ""
}

if [ -f "${CA_DEST}" ]; then
    echo ""
    echo "Root CA saved to: ${CA_DEST}"
    echo ""
    echo "Trust it once in your OS / browser:"
    echo "  macOS:   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ${CA_DEST}"
    echo "  Linux:   sudo cp ${CA_DEST} /usr/local/share/ca-certificates/caddy-local.crt && sudo update-ca-certificates"
    echo "  Windows: certutil -addstore -f Root ${CA_DEST}"
    echo "  Chrome/Firefox: import manually via browser Settings → Certificates."
    echo ""
fi

# ── 2. Set web.base.url in the Odoo DB ────────────────────────────────────
echo "Setting web.base.url = '${BASE_URL}' in database '${DB}'..."

python3 odoo-bin shell \
    --addons-path=/app/odoo/addons,/app/addons,/app/own_modules \
    -d "${DB}" \
    --no-http \
    <<'PYTHON'
env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://localhost')
env.cr.commit()
print("web.base.url updated.")
PYTHON

echo ""
echo "Done! Start Odoo with --proxy-mode:"
echo "  python3 odoo-bin --dev=all -d ${DB} --proxy-mode"
echo ""
echo "Then open: https://localhost"
