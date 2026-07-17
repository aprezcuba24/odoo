#!/bin/bash
# Provision a new Odoo tenant database (multi-tenant / Railway).
#
# Usage:
#   ./scripts/provision_tenant.sh TENANT_NAME [extra_modules...]
#
# Examples:
#   ./scripts/provision_tenant.sh cliente1
#   ./scripts/provision_tenant.sh cliente1 order_bridge,fs_attachment
#   ODOO_EXTRA_INIT_MODULES=order_bridge ./scripts/provision_tenant.sh cliente2
#
# Requires DATABASE_URL or PGHOST/PGUSER/PGPASSWORD (same as production).
# After provisioning, add TENANT_NAME to ODOO_TENANT_DATABASES on the Railway
# multi-tenant service so deploys run -u base against it.
#
# Naming convention for subdomain routing (ODOO_DBFILTER=^%d$):
#   cliente1.plataforma.com  →  database name "cliente1"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    sed -n '2,18p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage 0
fi

TENANT_NAME="${1:-}"
if [ -z "$TENANT_NAME" ]; then
    print_error "Falta el nombre del tenant (nombre de la base de datos)."
    usage 1
fi
shift || true

# Optional positional: comma-separated modules, else ODOO_EXTRA_INIT_MODULES
EXTRA_MODULES="${1:-${ODOO_EXTRA_INIT_MODULES:-}}"

if [ -z "${ODOO_ADDONS_PATH:-}" ]; then
    export ODOO_ADDONS_PATH="${REPO_ROOT}/odoo/addons,${REPO_ROOT}/addons,${REPO_ROOT}/own_modules,${REPO_ROOT}/oca"
fi

if [ -n "${DATABASE_URL:-}" ]; then
    eval "$(python3 -c "
from urllib.parse import urlparse
import os
url = urlparse(os.environ['DATABASE_URL'])
print(f'export PGHOST={url.hostname or \"localhost\"}')
print(f'export PGPORT={url.port or 5432}')
print(f'export PGUSER={url.username or \"odoo\"}')
print(f'export PGPASSWORD={url.password or \"\"}')
")"
fi

if [ -z "${PGHOST:-}" ]; then
    print_error "PGHOST / DATABASE_URL no configurados."
    exit 1
fi

DB_ARGS=()
DB_ARGS+=("--db_host=${PGHOST}")
DB_ARGS+=("--db_port=${PGPORT:-5432}")
if [ -n "${PGUSER:-}" ]; then
    DB_ARGS+=("-r" "${PGUSER}")
fi
if [ -n "${PGPASSWORD:-}" ]; then
    DB_ARGS+=("-w" "${PGPASSWORD}")
fi

INIT_ARGS=()
INIT_ARGS+=("--language=${DB_LANGUAGE:-es_ES}")
INIT_ARGS+=("--username=${DB_USERNAME:-admin}")
INIT_ARGS+=("--password=${DB_PASSWORD_ADMIN:-admin}")
if [ "${DB_WITH_DEMO:-false}" = "true" ]; then
    INIT_ARGS+=("--with-demo")
fi

print_info "Provisionando tenant '${TENANT_NAME}'..."
print_info "Ejecutando: odoo-bin db init ${TENANT_NAME}"

if ! "${REPO_ROOT}/odoo-bin" db "${DB_ARGS[@]}" init "${TENANT_NAME}" "${INIT_ARGS[@]}" --force; then
    print_error "Falló odoo-bin db init ${TENANT_NAME}"
    exit 1
fi

if [ -n "$EXTRA_MODULES" ]; then
    print_info "Instalando módulos: ${EXTRA_MODULES}"
    if ! "${REPO_ROOT}/odoo-bin" "${DB_ARGS[@]}" -d "${TENANT_NAME}" -i "${EXTRA_MODULES}" --stop-after-init --no-http; then
        print_warn "Falló la instalación de módulos extra; la BD base existe. Revisa logs."
    fi
fi

ATTACHMENT_MODE="${ODOO_ATTACHMENT_STORAGE:-db}"
if [ "$ATTACHMENT_MODE" != "s3" ]; then
    print_info "Configurando ir_attachment.location=db en '${TENANT_NAME}'..."
    TARGET_DB="$TENANT_NAME" python3 << 'PY'
import os
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2

target_db = os.environ["TARGET_DB"]
try:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        parsed = urlparse(db_url)
        conn = psycopg2.connect(urlunparse(parsed._replace(path=f"/{target_db}")))
    else:
        conn = psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=int(os.environ.get("PGPORT", "5432")),
            database=target_db,
            user=os.environ.get("PGUSER", "odoo"),
            password=os.environ.get("PGPASSWORD", ""),
        )
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ir_config_parameter (key, value)
        VALUES ('ir_attachment.location', 'db')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """
    )
    conn.commit()
    cur.close()
    conn.close()
    print("[INFO] ir_attachment.location=db OK")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PY
fi

print_info "Tenant '${TENANT_NAME}' listo."
print_info "Siguiente:"
echo "  1. Añade '${TENANT_NAME}' a ODOO_TENANT_DATABASES en el servicio Railway multi-tenant."
echo "  2. Subdominio: ${TENANT_NAME}.<tu-dominio> (wildcard DNS + Railway)."
echo "  3. Dominio custom (opcional): registra el dominio en Railway y añádelo a ODOO_TENANT_DOMAIN_MAP."
echo "     Ejemplo: ODOO_TENANT_DOMAIN_MAP={\"tienda.com\":\"${TENANT_NAME}\"}"
