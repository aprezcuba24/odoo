#!/bin/bash
# Provision a new Odoo tenant database (multi-tenant / Railway).
#
# Idempotent:
#   - missing DB      → create + init
#   - incomplete DB   → drop + recreate + init
#   - ready Odoo DB   → skip init; optionally install extra modules / attachment config
#
# Usage:
#   ./scripts/provision_tenant.sh TENANT_NAME [extra_modules...]
#
# Examples:
#   ./scripts/provision_tenant.sh cliente1
#   ./scripts/provision_tenant.sh cliente1 order_bridge,fs_attachment
#   ODOO_EXTRA_INIT_MODULES=order_bridge ./scripts/provision_tenant.sh cliente2
#
# If ORDER_BRIDGE_BANNER_S3_BUCKET or ODOO_S3_BUCKET is set, the script also
# installs fs_attachment+order_bridge (if missing) and provisions fs.storage
# for banners + image attachment fields (provision_media_fs_storage).
#
# Requires DATABASE_URL or PGHOST/PGUSER/PGPASSWORD (same as production).
# After provisioning, add TENANT_NAME to ODOO_TENANT_DATABASES on the Railway
# multi-tenant service so deploys run -u base against it.
#
# Naming convention for subdomain routing (ODOO_DBFILTER=^%d$):
#   cliente1.plataforma.com  →  database name "cliente1"
#
# Force recreate even if ready: PROVISION_FORCE_RECREATE=true ./scripts/provision_tenant.sh demo
#
# Media S3: if ORDER_BRIDGE_BANNER_S3_BUCKET or ODOO_S3_BUCKET is set, installs
# fs_attachment+order_bridge (merged into EXTRA_MODULES) and runs
# provision_media_fs_storage (banners + image fields). Prefer
# ODOO_ATTACHMENT_STORAGE=s3 so attachments are not forced to PostgreSQL.
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
    sed -n '2,24p' "$0" | sed 's/^# \?//'
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
if ! [[ "$TENANT_NAME" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ ]]; then
    print_error "Nombre de tenant inválido '${TENANT_NAME}' (usa letras, números y _; debe empezar por letra)."
    exit 1
fi
shift || true

# Optional positional: comma-separated modules, else ODOO_EXTRA_INIT_MODULES
EXTRA_MODULES="${1:-${ODOO_EXTRA_INIT_MODULES:-}}"

# When a banner S3 bucket is configured, ensure fs_attachment + order_bridge are installed.
BANNER_S3_BUCKET="${ORDER_BRIDGE_BANNER_S3_BUCKET:-${ODOO_S3_BUCKET:-}}"
if [ -n "$BANNER_S3_BUCKET" ]; then
    for _mod in fs_attachment order_bridge; do
        case ",${EXTRA_MODULES}," in
            *",${_mod},"*) ;;
            *)
                if [ -z "$EXTRA_MODULES" ]; then
                    EXTRA_MODULES="${_mod}"
                else
                    EXTRA_MODULES="${EXTRA_MODULES},${_mod}"
                fi
                ;;
        esac
    done
fi

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

# Returns: missing | incomplete | ready
tenant_db_status() {
    TARGET_DB="$TENANT_NAME" python3 << 'PY'
import os
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2

name = os.environ["TARGET_DB"]

def connect(dbname):
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        parsed = urlparse(db_url)
        return psycopg2.connect(urlunparse(parsed._replace(path=f"/{dbname}")))
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        database=dbname,
        user=os.environ.get("PGUSER", "odoo"),
        password=os.environ.get("PGPASSWORD", ""),
    )

try:
    conn = connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
except Exception as e:
    print(f"error checking pg_database: {e}", file=sys.stderr)
    sys.exit(2)

if not exists:
    print("missing")
    sys.exit(0)

try:
    conn = connect(name)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'ir_module_module'
        )
        """
    )
    has_modules = cur.fetchone()[0]
    if not has_modules:
        print("incomplete")
        cur.close()
        conn.close()
        sys.exit(0)
    cur.execute(
        """
        SELECT state FROM ir_module_module WHERE name = 'base' LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row[0] == "installed":
        print("ready")
    else:
        print("incomplete")
except Exception:
    # Exists but cannot query → treat as broken/incomplete
    print("incomplete")
PY
}

drop_tenant_database() {
    print_warn "Eliminando base '${TENANT_NAME}' (conexiones activas se terminan)..."
    TARGET_DB="$TENANT_NAME" python3 << 'PY'
import os
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2

name = os.environ["TARGET_DB"]

def connect(dbname):
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        parsed = urlparse(db_url)
        return psycopg2.connect(urlunparse(parsed._replace(path=f"/{dbname}")))
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        database=dbname,
        user=os.environ.get("PGUSER", "odoo"),
        password=os.environ.get("PGPASSWORD", ""),
    )

try:
    conn = connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s AND pid <> pg_backend_pid()
        """,
        (name,),
    )
    from psycopg2 import sql as pgsql

    cur.execute(pgsql.SQL("DROP DATABASE IF EXISTS {}").format(pgsql.Identifier(name)))
    cur.close()
    conn.close()
    print(f"[INFO] Base '{name}' eliminada.")
except Exception as e:
    print(f"Error dropping database: {e}", file=sys.stderr)
    sys.exit(1)
PY
}

configure_attachments() {
    ATTACHMENT_MODE="${ODOO_ATTACHMENT_STORAGE:-db}"
    if [ "$ATTACHMENT_MODE" = "s3" ]; then
        print_info "ODOO_ATTACHMENT_STORAGE=s3: no se fuerza ir_attachment.location=db."
        return 0
    fi
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
}

install_extra_modules() {
    if [ -z "$EXTRA_MODULES" ]; then
        return 0
    fi
    print_info "Instalando módulos: ${EXTRA_MODULES}"
    if ! "${REPO_ROOT}/odoo-bin" "${DB_ARGS[@]}" -d "${TENANT_NAME}" -i "${EXTRA_MODULES}" --stop-after-init --no-http; then
        print_warn "Falló la instalación de módulos extra; la BD base existe. Revisa logs."
    fi
}

provision_banner_s3() {
    if [ -z "${BANNER_S3_BUCKET:-}" ]; then
        return 0
    fi
    local mt_label="single-tenant (directory_path=${BANNER_S3_BUCKET})"
    case "$(printf '%s' "${ODOO_MULTI_TENANT:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) mt_label="multi-tenant (directory_path=${BANNER_S3_BUCKET}/{db_name})" ;;
    esac
    print_info "Sincronizando fs.storage S3 (banners + imágenes) en '${TENANT_NAME}' bucket=${BANNER_S3_BUCKET} ${mt_label}..."
    if printf '%s\n' \
        "from odoo.addons.order_bridge import hooks as obhooks" \
        "obhooks.provision_media_fs_storage(env)" \
        | python3 "${REPO_ROOT}/odoo-bin" shell "${DB_ARGS[@]}" -d "${TENANT_NAME}" --no-http; then
        print_info "Provision S3 media completada en '${TENANT_NAME}'."
    else
        print_warn "Provision S3 media falló en '${TENANT_NAME}'; revisa credenciales y que fs_attachment + order_bridge estén instalados."
    fi
}

# ---------------------------------------------------------------------------
print_info "Provisionando tenant '${TENANT_NAME}' (idempotente)..."

STATUS="$(tenant_db_status)" || {
    print_error "No se pudo consultar el estado de '${TENANT_NAME}'."
    exit 1
}

FORCE_RECREATE=false
case "$(printf '%s' "${PROVISION_FORCE_RECREATE:-}" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|on) FORCE_RECREATE=true ;;
esac

if [ "$FORCE_RECREATE" = true ] && [ "$STATUS" != "missing" ]; then
    print_warn "PROVISION_FORCE_RECREATE=true → se recreará '${TENANT_NAME}'."
    STATUS=incomplete
fi

case "$STATUS" in
    ready)
        print_info "La base '${TENANT_NAME}' ya está inicializada (Odoo ready). Se omite db init."
        ;;
    incomplete)
        print_warn "La base '${TENANT_NAME}' existe pero está incompleta o rota. Se recrea."
        drop_tenant_database
        print_info "Ejecutando: odoo-bin db init ${TENANT_NAME}"
        if ! "${REPO_ROOT}/odoo-bin" db "${DB_ARGS[@]}" init --force "${TENANT_NAME}" "${INIT_ARGS[@]}"; then
            print_error "Falló odoo-bin db init ${TENANT_NAME}"
            exit 1
        fi
        ;;
    missing)
        print_info "Ejecutando: odoo-bin db init ${TENANT_NAME}"
        if ! "${REPO_ROOT}/odoo-bin" db "${DB_ARGS[@]}" init --force "${TENANT_NAME}" "${INIT_ARGS[@]}"; then
            print_error "Falló odoo-bin db init ${TENANT_NAME}"
            exit 1
        fi
        ;;
    *)
        print_error "Estado desconocido: ${STATUS}"
        exit 1
        ;;
esac

install_extra_modules
configure_attachments
provision_banner_s3

print_info "Tenant '${TENANT_NAME}' listo."
print_info "Siguiente:"
echo "  1. Añade '${TENANT_NAME}' a ODOO_TENANT_DATABASES en el servicio Railway multi-tenant."
echo "  2. Subdominio: ${TENANT_NAME}.<tu-dominio> (wildcard DNS + Railway)."
echo "  3. Dominio custom / URL Railway: ODOO_TENANT_DOMAIN_MAP={\"host\":\"${TENANT_NAME}\"}"
echo "  4. Recrear desde cero aunque esté ready: PROVISION_FORCE_RECREATE=true $0 ${TENANT_NAME}"
