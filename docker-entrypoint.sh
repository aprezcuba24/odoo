#!/bin/bash
# Script de entrada para Docker o runtime PaaS (Railway, etc.)
# Inicializa/actualiza la(s) base(s) de datos y luego inicia Gunicorn.
# Single-tenant (default): una BD desde DATABASE_URL / PGDATABASE.
# Multi-tenant (ODOO_MULTI_TENANT=true): upgrade de tenants listados o detectados; sin init de la BD del path de DATABASE_URL.
set -e

# Resolve the directory that contains this script so paths work both in Docker
# (/app as WORKDIR) and in a runtime PaaS deployment (arbitrary working dir).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Odoo addons path: core + community + this repo's custom addons (override with ODOO_ADDONS_PATH)
if [ -z "${ODOO_ADDONS_PATH:-}" ]; then
    export ODOO_ADDONS_PATH="${SCRIPT_DIR}/odoo/addons,${SCRIPT_DIR}/addons,${SCRIPT_DIR}/own_modules,${SCRIPT_DIR}/oca"
fi

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

is_multi_tenant() {
    case "$(printf '%s' "${ODOO_MULTI_TENANT:-}" | tr '[:upper:]' '[:lower:]')" in
        true|1|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

# If DATABASE_URL is provided, parse it into individual PG* variables
if [ -n "$DATABASE_URL" ]; then
    print_info "DATABASE_URL detectada. Parseando configuración de conexión..."
    eval $(python3 -c "
from urllib.parse import urlparse
import os
url = urlparse(os.environ['DATABASE_URL'])
print(f'export PGHOST={url.hostname or \"localhost\"}')
print(f'export PGPORT={url.port or 5432}')
print(f'export PGUSER={url.username or \"odoo\"}')
print(f'export PGPASSWORD={url.password or \"\"}')
db = url.path.lstrip('/')
print(f'export PGDATABASE={db}')
")
fi

# Verificar que las variables de entorno de base de datos están configuradas
if [ -z "$DATABASE_URL" ] && [ -z "$PGDATABASE" ]; then
    print_error "PGDATABASE no está configurada. Por favor, configura DATABASE_URL o las variables de entorno individuales de la base de datos."
    exit 1
fi

if [ -z "$DATABASE_URL" ] && [ -z "$PGHOST" ]; then
    print_error "PGHOST no está configurada. Por favor, configura DATABASE_URL o las variables de entorno individuales de la base de datos."
    exit 1
fi

# Construir array de argumentos de conexión para odoo-bin
DB_ARGS=()
if [ -n "$PGHOST" ]; then
    DB_ARGS+=("--db_host=${PGHOST}")
fi
if [ -n "$PGPORT" ]; then
    DB_ARGS+=("--db_port=${PGPORT}")
fi
if [ -n "$PGUSER" ]; then
    DB_ARGS+=("-r" "${PGUSER}")
fi
if [ -n "$PGPASSWORD" ]; then
    DB_ARGS+=("-w" "${PGPASSWORD}")
fi

# Verificar si una base de datos concreta está inicializada (tabla ir_module_module).
# Uso: check_database_initialized [dbname]  — por defecto PGDATABASE
check_database_initialized() {
    local target_db="${1:-$PGDATABASE}"
    print_info "Verificando si la base de datos '${target_db}' está inicializada..."

    TARGET_DB="$target_db" python3 << 'EOF'
import psycopg2
import sys
import os
from urllib.parse import urlparse, urlunparse

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
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'ir_module_module'
        );
        """
    )
    exists = cur.fetchone()[0]
    cur.close()
    conn.close()
    sys.exit(0 if exists else 1)
except psycopg2.OperationalError as e:
    print(f"Base de datos no accesible: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error verificando base de datos: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Listar bases Odoo del servidor PG (excluye templates y BD default de Railway).
# Si ODOO_TENANT_DATABASES está definida, usa esa lista (coma-separada).
list_tenant_databases() {
    if [ -n "${ODOO_TENANT_DATABASES:-}" ]; then
        echo "${ODOO_TENANT_DATABASES}" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$'
        return 0
    fi

    python3 << 'EOF'
import os
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2

EXCLUDE = {"postgres", "template0", "template1", "railway"}

try:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        parsed = urlparse(db_url)
        conn = psycopg2.connect(urlunparse(parsed._replace(path="/postgres")))
    else:
        conn = psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=int(os.environ.get("PGPORT", "5432")),
            database="postgres",
            user=os.environ.get("PGUSER", "odoo"),
            password=os.environ.get("PGPASSWORD", ""),
        )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        SELECT datname FROM pg_database
        WHERE datallowconn
          AND NOT datistemplate
          AND datname <> ALL(%s)
        ORDER BY datname
        """,
        (list(EXCLUDE),),
    )
    names = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    odoo_dbs = []
    for name in names:
        try:
            if db_url:
                parsed = urlparse(db_url)
                c = psycopg2.connect(urlunparse(parsed._replace(path=f"/{name}")))
            else:
                c = psycopg2.connect(
                    host=os.environ.get("PGHOST", "localhost"),
                    port=int(os.environ.get("PGPORT", "5432")),
                    database=name,
                    user=os.environ.get("PGUSER", "odoo"),
                    password=os.environ.get("PGPASSWORD", ""),
                )
            cur2 = c.cursor()
            cur2.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'ir_module_module'
                );
                """
            )
            if cur2.fetchone()[0]:
                odoo_dbs.append(name)
            cur2.close()
            c.close()
        except Exception:
            continue

    for name in odoo_dbs:
        print(name)
except Exception as e:
    print(f"Error listando bases tenant: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Función para inicializar la base de datos
init_database() {
    local target_db="${1:-$PGDATABASE}"
    print_info "Inicializando base de datos '${target_db}' desde cero..."

    INIT_ARGS=()
    if [ -n "$DB_LANGUAGE" ]; then
        INIT_ARGS+=("--language=${DB_LANGUAGE}")
    else
        INIT_ARGS+=("--language=es_ES")
    fi
    if [ -n "$DB_USERNAME" ]; then
        INIT_ARGS+=("--username=${DB_USERNAME}")
    else
        INIT_ARGS+=("--username=admin")
    fi
    if [ -n "$DB_PASSWORD_ADMIN" ]; then
        INIT_ARGS+=("--password=${DB_PASSWORD_ADMIN}")
    else
        INIT_ARGS+=("--password=admin")
    fi
    if [ "$DB_WITH_DEMO" = "true" ]; then
        INIT_ARGS+=("--with-demo")
    fi

    print_info "Ejecutando: odoo-bin db init ${target_db} con argumentos de conexión..."
    if "$SCRIPT_DIR/odoo-bin" db "${DB_ARGS[@]}" init "${target_db}" "${INIT_ARGS[@]}" --force; then
        print_info "Base de datos '${target_db}' inicializada correctamente."
        return 0
    else
        print_error "Error al inicializar la base de datos '${target_db}'."
        return 1
    fi
}

# Función para actualizar módulos (base)
update_database() {
    local target_db="${1:-$PGDATABASE}"
    print_info "Actualizando esquema de la base de datos '${target_db}'..."

    print_info "Ejecutando: odoo-bin -d ${target_db} -u base..."
    if "$SCRIPT_DIR/odoo-bin" "${DB_ARGS[@]}" -d "${target_db}" -u base --stop-after-init --no-http; then
        print_info "Base de datos '${target_db}' actualizada correctamente."
        return 0
    else
        print_error "Error al actualizar la base de datos '${target_db}'."
        return 1
    fi
}

# PaaS: el filesystem es efímero; el filestore se pierde en cada deploy.
# Fuerza almacenamiento en BD y elimina bundles de assets que apuntan a ficheros ya borrados.
configure_attachment_storage() {
    local target_db="${1:-$PGDATABASE}"
    print_info "Configurando almacenamiento de adjuntos para PaaS en '${target_db}' (ir_attachment.location=db)..."

    TARGET_DB="$target_db" python3 << 'EOF'
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
    cur.execute(
        """
        DELETE FROM ir_attachment
        WHERE store_fname IS NOT NULL
          AND url LIKE '/web/assets/%%';
        """
    )
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    print(f"[INFO] Eliminados {deleted} adjuntos de bundles /web/assets (se regeneran al servir).")
except Exception as e:
    print(f"Error configurando adjuntos PaaS: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Migra adjuntos que siguen en filestore a la base de datos (tras cambiar ir_attachment.location).
migrate_attachments_to_db() {
    local target_db="${1:-$PGDATABASE}"
    print_info "Migrando adjuntos existentes del filestore a la base de datos '${target_db}' (force_storage)..."

    if printf '%s\n' "env['ir.attachment'].force_storage()" | python3 "$SCRIPT_DIR/odoo-bin" shell "${DB_ARGS[@]}" -d "${target_db}" --no-http; then
        print_info "Migración de adjuntos completada en '${target_db}'."
    else
        print_warn "force_storage() falló en '${target_db}'; revisa los logs. Los adjuntos pueden seguir referenciando rutas de filestore inexistentes."
    fi
}

install_extra_modules() {
    local target_db="${1:-$PGDATABASE}"
    if [ -z "${ODOO_EXTRA_INIT_MODULES:-}" ]; then
        return 0
    fi
    print_info "Instalación opcional de módulos en '${target_db}' (ODOO_EXTRA_INIT_MODULES=${ODOO_EXTRA_INIT_MODULES})..."
    if "$SCRIPT_DIR/odoo-bin" "${DB_ARGS[@]}" -d "${target_db}" -i "${ODOO_EXTRA_INIT_MODULES}" --stop-after-init --no-http; then
        print_info "Módulos extra procesados en '${target_db}'."
    else
        print_warn "Fallo al ejecutar -i ODOO_EXTRA_INIT_MODULES en '${target_db}'; revisa logs."
    fi
}

provision_banner_s3() {
    local target_db="${1:-$PGDATABASE}"
    local banner_bucket="${ORDER_BRIDGE_BANNER_S3_BUCKET:-${ODOO_S3_BUCKET:-}}"
    if [ -z "$banner_bucket" ]; then
        return 0
    fi
    local mt_flag="${ODOO_MULTI_TENANT:-}"
    local mt_label="single-tenant (directory_path=${banner_bucket})"
    case "$(printf '%s' "$mt_flag" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) mt_label="multi-tenant (directory_path=${banner_bucket}/{db_name})" ;;
    esac
    print_info "Sincronizando fs.storage S3 (banners + imágenes) en '${target_db}' bucket=${banner_bucket} ${mt_label}..."
    if printf '%s\n' \
        "from odoo.addons.order_bridge import hooks as obhooks" \
        "obhooks.provision_media_fs_storage(env)" \
        | python3 "$SCRIPT_DIR/odoo-bin" shell "${DB_ARGS[@]}" -d "${target_db}" --no-http; then
        print_info "Provision S3 media (fs.storage ${banner_bucket}) completada en '${target_db}'."
    else
        print_warn "Provision S3 media falló en '${target_db}'; revisa credenciales y que fs_attachment + order_bridge estén instalados."
    fi
}

prepare_tenant_database() {
    local target_db="$1"
    ATTACHMENT_STORAGE_MODE="${ODOO_ATTACHMENT_STORAGE:-db}"
    if [ "$ATTACHMENT_STORAGE_MODE" = "s3" ]; then
        print_info "ODOO_ATTACHMENT_STORAGE=s3: no se fuerza ir_attachment.location=db ni force_storage() en '${target_db}'."
    else
        configure_attachment_storage "${target_db}"
        migrate_attachments_to_db "${target_db}"
    fi
    install_extra_modules "${target_db}"
    provision_banner_s3 "${target_db}"
}

# SKIP_DB_UPGRADE=true|1|yes omite odoo-bin -u base (emergencia / falta de RAM en deploy)
skip_db_upgrade() {
    case "$(printf '%s' "${SKIP_DB_UPGRADE:-}" | tr '[:upper:]' '[:lower:]')" in
        true|1|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------
print_info "Iniciando proceso de inicialización/actualización de base de datos..."

if is_multi_tenant; then
    print_info "Modo multi-tenant (ODOO_MULTI_TENANT=true). No se inicializa la BD del path de DATABASE_URL."
    mapfile -t TENANT_DBS < <(list_tenant_databases)
    if [ "${#TENANT_DBS[@]}" -eq 0 ]; then
        print_warn "No hay bases tenant para actualizar."
        print_warn "Provisiona al menos una con scripts/provision_tenant.sh y/o define ODOO_TENANT_DATABASES."
    else
        print_info "Bases tenant: ${TENANT_DBS[*]}"
        for tenant_db in "${TENANT_DBS[@]}"; do
            if ! check_database_initialized "${tenant_db}" 2>/dev/null; then
                print_warn "La base '${tenant_db}' no está inicializada como Odoo; se omite (usa scripts/provision_tenant.sh)."
                continue
            fi
            if skip_db_upgrade; then
                print_warn "SKIP_DB_UPGRADE activado: se omite -u base en '${tenant_db}'."
            else
                if ! update_database "${tenant_db}"; then
                    print_warn "Error al actualizar '${tenant_db}'. Continuando con las demás..."
                fi
            fi
            prepare_tenant_database "${tenant_db}"
        done
    fi
    print_info "Multi-tenant listo. Iniciando Gunicorn..."
else
    # Single-tenant (comportamiento histórico)
    if check_database_initialized 2>/dev/null; then
        print_info "La base de datos '${PGDATABASE}' ya existe y está inicializada."
        if skip_db_upgrade; then
            print_warn "SKIP_DB_UPGRADE activado: se omite odoo-bin -u base en este arranque."
            print_warn "Ejecuta el upgrade manualmente contra esta misma base (odoo-bin -u base) con RAM suficiente."
        else
            print_info "Actualizando esquema de la base de datos (esto se ejecuta en cada deploy)..."
            if ! update_database; then
                print_warn "Error al actualizar la base de datos. Continuando de todas formas..."
                print_warn "La aplicación se iniciará pero puede que el esquema no esté actualizado."
            fi
        fi
    else
        print_warn "La base de datos '${PGDATABASE}' no está inicializada o no existe."
        print_info "Inicializando base de datos desde cero (primera vez)..."
        if ! init_database; then
            print_error "Error al inicializar la base de datos. Abortando."
            exit 1
        fi
    fi

    prepare_tenant_database "${PGDATABASE}"
    print_info "Base de datos lista. Iniciando Gunicorn..."
fi

# Ejecutar Gunicorn (reemplaza el proceso actual)
# Usar odoo-wsgi:application que tiene la configuración correcta para websockets
# Los logs van a stdout/stderr para PaaS
exec gunicorn odoo-wsgi:application \
    --pythonpath "$SCRIPT_DIR" \
    --config "$SCRIPT_DIR/gunicorn.conf.py" \
    --access-logfile - \
    --error-logfile -
