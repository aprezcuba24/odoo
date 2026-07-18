#!/bin/bash
# Verify OCA fs.storage S3 provisioning for Tienda Apk media (banners + images).
#
# Works for single-tenant and multi-tenant: pass the database name to check.
#
# Usage:
#   ./scripts/verify_s3_storage.sh <db_name>
#
# Examples:
#   # Multi-tenant tenant DB
#   ./scripts/verify_s3_storage.sh cliente1
#
#   # Single-tenant production DB (often the DATABASE_URL path, e.g. railway)
#   ./scripts/verify_s3_storage.sh railway
#
# Reads ORDER_BRIDGE_* / ODOO_S3_* / AWS_* / ODOO_MULTI_TENANT from the environment.
# Does not print secrets.
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

DB_NAME="${1:-}"
if [ -z "$DB_NAME" ]; then
    print_error "Falta el nombre de la base de datos."
    usage 1
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

print_info "Verificando S3 media storage en BD '${DB_NAME}'..."

VERIFY_PY="$(cat <<'PY'
from odoo.addons.order_bridge import hooks as obhooks

bucket = obhooks._media_s3_bucket()
mt = obhooks._multi_tenant_enabled()
expected_path = obhooks._media_directory_path(bucket) if bucket else "(no bucket)"
access, secret = obhooks._s3_credentials()

print("=== Env / expected layout ===")
print(f"ODOO_MULTI_TENANT={mt}")
print(f"bucket={bucket or '(unset)'}")
print(f"directory_path_template={expected_path}")
print(f"credentials_present={bool(access and secret)}")
print(f"db_name={env.cr.dbname}")
if mt and bucket:
    print(f"resolved_prefix={bucket}/{env.cr.dbname}/")
elif bucket:
    print(f"resolved_prefix={bucket}/ (bucket root)")

fs_mod = env["ir.module.module"].sudo().search([("name", "=", "fs_attachment")], limit=1)
print()
print("=== Modules ===")
print(f"fs_attachment={fs_mod.state if fs_mod else 'missing'}")
ob_mod = env["ir.module.module"].sudo().search([("name", "=", "order_bridge")], limit=1)
print(f"order_bridge={ob_mod.state if ob_mod else 'missing'}")

Storage = env["fs.storage"].sudo()
storage = Storage.search([("code", "=", obhooks.MEDIA_FS_STORAGE_CODE)], limit=1)
print()
print("=== fs.storage ===")
if not storage:
    print(f"MISSING code={obhooks.MEDIA_FS_STORAGE_CODE}")
    print("Run: provision_media_fs_storage(env) after setting bucket + credentials.")
else:
    field_count = len((storage.field_xmlids or "").split(",")) if storage.field_xmlids else 0
    print(f"code={storage.code}")
    print(f"name={storage.name}")
    print(f"protocol={storage.protocol}")
    print(f"directory_path={storage.directory_path}")
    print(f"resolved_directory_path={storage.get_directory_path()}")
    print(f"model_xmlids={storage.model_xmlids}")
    print(f"field_xmlids_count={field_count}")
    print(f"use_as_default_for_attachments={storage.use_as_default_for_attachments}")
    if storage.field_xmlids:
        sample = ",".join(storage.field_xmlids.split(",")[:5])
        print(f"field_xmlids_sample={sample}")
    ok_path = (
        storage.directory_path == expected_path
        if bucket
        else False
    )
    ok_model = storage.model_xmlids == obhooks.BANNER_MODEL_XMLID
    print(f"path_matches_env={ok_path}")
    print(f"banner_model_linked={ok_model}")
    print()
    print("=== S3 connection test ===")
    try:
        storage._test_config(storage.check_connection_method or "marker_file")
        print("connection=OK")
    except Exception as e:
        print(f"connection=FAIL: {e}")

print()
print("=== Recent attachments (banner / product images) ===")
Att = env["ir.attachment"].sudo()
domain = [
    "|",
    ("res_model", "=", "order_bridge.banner"),
    ("res_field", "ilike", "image"),
]
atts = Att.search(domain, order="id desc", limit=8)
if not atts:
    print("(none found — upload a new product/banner image after provisioning)")
else:
    for a in atts:
        code = a.fs_storage_code or "(none)"
        fname = a.store_fname or ("db" if a.db_datas else "(empty)")
        print(
            f"id={a.id} res={a.res_model}.{a.res_field or '?'} "
            f"fs_storage_code={code} store_fname={fname[:80]}"
        )

print()
print("=== Checklist ===")
print("1. ODOO_ATTACHMENT_STORAGE=s3 (so entrypoint does not force DB)")
print("2. Bucket + credentials set; fs_attachment + order_bridge installed")
print("3. Upload a NEW product image and banner; old ones stay in DB until re-saved")
print("4. ST: objects at bucket root | MT: objects under <bucket>/<db_name>/")
PY
)"

# Odoo 19: subcommand must come before options (odoo-bin shell -d ...).
if printf '%s\n' "$VERIFY_PY" | python3 "${REPO_ROOT}/odoo-bin" shell "${DB_ARGS[@]}" -d "${DB_NAME}" --no-http; then
    print_info "Verificación terminada para '${DB_NAME}'."
else
    print_error "Falló odoo shell contra '${DB_NAME}'."
    exit 1
fi
