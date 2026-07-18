#!/bin/bash
# Force-create/update fs.storage S3 for Tienda Apk media on one database.
#
# Usage:
#   ./scripts/provision_s3_storage.sh <db_name>
#
# Examples:
#   ./scripts/provision_s3_storage.sh demo
#   ./scripts/provision_s3_storage.sh railway
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

DB_NAME="${1:-}"
if [ -z "$DB_NAME" ] || [ "$DB_NAME" = "-h" ] || [ "$DB_NAME" = "--help" ]; then
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    if [ -z "$DB_NAME" ]; then
        exit 1
    fi
    exit 0
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

DB_ARGS=(--db_host="${PGHOST}" --db_port="${PGPORT:-5432}")
if [ -n "${PGUSER:-}" ]; then
    DB_ARGS+=(-r "${PGUSER}")
fi
if [ -n "${PGPASSWORD:-}" ]; then
    DB_ARGS+=(-w "${PGPASSWORD}")
fi

print_info "Provisionando fs.storage S3 en '${DB_NAME}'..."

PROVISION_PY="$(cat <<'PY'
import traceback

from odoo.addons.order_bridge import hooks as h

print(f"bucket={h._media_s3_bucket()!r}")
print(f"multi_tenant={h._multi_tenant_enabled()}")
print(f"directory_path={h._media_directory_path(h._media_s3_bucket()) if h._media_s3_bucket() else None!r}")
ak, sk = h._s3_credentials()
print(f"credentials_present={bool(ak and sk)}")

try:
    storage = h.provision_media_fs_storage(env)
    if not storage:
        print("RESULT=skipped (hook returned None — check logs above / env / modules)")
    else:
        env.cr.commit()
        print(f"RESULT=ok id={storage.id} code={storage.code}")
        print(f"directory_path={storage.directory_path}")
        print(f"resolved={storage.get_directory_path()}")
        print(f"model_xmlids={storage.model_xmlids}")
        n = len((storage.field_xmlids or '').split(',')) if storage.field_xmlids else 0
        print(f"field_xmlids_count={n}")
except Exception:
    traceback.print_exc()
    print("RESULT=error")
    raise
PY
)"

if printf '%s\n' "$PROVISION_PY" | python3 "${REPO_ROOT}/odoo-bin" shell "${DB_ARGS[@]}" -d "${DB_NAME}" --no-http; then
    print_info "Provision terminado. Ejecuta: ./scripts/verify_s3_storage.sh ${DB_NAME}"
else
    print_error "Provision falló en '${DB_NAME}' (ver traceback arriba)."
    exit 1
fi
