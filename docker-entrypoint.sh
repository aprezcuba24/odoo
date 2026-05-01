#!/bin/bash
# Script de entrada para Docker o runtime PaaS (Seenode, Render, Railway?)
# Inicializa/actualiza la base de datos y luego inicia Gunicorn.
set -e

# Resolve the directory that contains this script so paths work both in Docker
# (/app as WORKDIR) and in a runtime PaaS deployment (arbitrary working dir).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Odoo addons path: core + community + this repo's custom addons (override with ODOO_ADDONS_PATH).
if [ -z "${ODOO_ADDONS_PATH:-}" ]; then
    export ODOO_ADDONS_PATH="${SCRIPT_DIR}/odoo/addons,${SCRIPT_DIR}/addons,${SCRIPT_DIR}/own_modules"
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

# If DATABASE_URL is provided, parse it into individual PG* variables
if [ -n "$DATABASE_URL" ]; then
    print_info "DATABASE_URL detectada. Parseando configuraci?n de conexi?n..."
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

# Verificar que las variables de entorno de base de datos est?n configuradas
if [ -z "$DATABASE_URL" ] && [ -z "$PGDATABASE" ]; then
    print_error "PGDATABASE no est? configurada. Por favor, configura DATABASE_URL o las variables de entorno individuales de la base de datos."
    exit 1
fi

if [ -z "$DATABASE_URL" ] && [ -z "$PGHOST" ]; then
    print_error "PGHOST no est? configurada. Por favor, configura DATABASE_URL o las variables de entorno individuales de la base de datos."
    exit 1
fi

# Construir array de argumentos de conexi?n para odoo-bin
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

# Funci?n para verificar si la base de datos est? inicializada
check_database_initialized() {
    print_info "Verificando si la base de datos '${PGDATABASE}' est? inicializada..."

    # Usar Python para verificar si existe la tabla ir_module_module
    python3 << EOF
import psycopg2
import sys
import os

try:
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST', 'localhost'),
            port=int(os.environ.get('PGPORT', '5432')),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER', 'odoo'),
            password=os.environ.get('PGPASSWORD', '')
        )
    cur = conn.cursor()
    # Verificar si existe la tabla ir_module_module (indica que Odoo est? inicializado)
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'ir_module_module'
        );
    """)
    exists = cur.fetchone()[0]
    cur.close()
    conn.close()
    sys.exit(0 if exists else 1)
except psycopg2.OperationalError as e:
    # Base de datos no existe o no se puede conectar
    print(f"Base de datos no accesible: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error verificando base de datos: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Funci?n para inicializar la base de datos
init_database() {
    print_info "Inicializando base de datos '${PGDATABASE}' desde cero..."

    # Par?metros adicionales para inicializaci?n
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

    # Ejecutar inicializaci?n
    print_info "Ejecutando: odoo-bin db init ${PGDATABASE} con argumentos de conexi?n..."
    if "$SCRIPT_DIR/odoo-bin" db "${DB_ARGS[@]}" init "${PGDATABASE}" "${INIT_ARGS[@]}" --force; then
        print_info "Base de datos '${PGDATABASE}' inicializada correctamente."
        return 0
    else
        print_error "Error al inicializar la base de datos '${PGDATABASE}'."
        return 1
    fi
}

# Funci?n para actualizar todos los m?dulos
update_database() {
    print_info "Actualizando esquema de la base de datos '${PGDATABASE}'..."

    # Actualizar todos los m?dulos (base actualiza todo)
    print_info "Ejecutando: odoo-bin module upgrade base..."
    if "$SCRIPT_DIR/odoo-bin" "${DB_ARGS[@]}" -d "${PGDATABASE}" -u base --stop-after-init --no-http; then
        print_info "Base de datos '${PGDATABASE}' actualizada correctamente."
        return 0
    else
        print_error "Error al actualizar la base de datos '${PGDATABASE}'."
        return 1
    fi
}

# PaaS: el filesystem es efímero; el filestore se pierde en cada deploy.
# Fuerza almacenamiento en BD y elimina bundles de assets que apuntan a ficheros ya borrados.
configure_attachment_storage() {
    print_info "Configurando almacenamiento de adjuntos para PaaS (ir_attachment.location=db)..."

    python3 << 'EOF'
import os
import sys

import psycopg2

try:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=int(os.environ.get("PGPORT", "5432")),
            database=os.environ.get("PGDATABASE"),
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
    print_info "Migrando adjuntos existentes del filestore a la base de datos (force_storage)..."

    if printf '%s\n' "env['ir.attachment'].force_storage()" | "$SCRIPT_DIR/odoo-bin" "${DB_ARGS[@]}" -d "${PGDATABASE}" shell --no-http; then
        print_info "Migración de adjuntos completada."
    else
        print_warn "force_storage() falló; revisa los logs. Los adjuntos pueden seguir referenciando rutas de filestore inexistentes."
    fi
}

# Proceso principal
print_info "Iniciando proceso de inicializaci?n/actualizaci?n de base de datos..."

# Verificar si la base de datos est? inicializada
if check_database_initialized 2>/dev/null; then
    print_info "La base de datos '${PGDATABASE}' ya existe y est? inicializada."
    print_info "Actualizando esquema de la base de datos (esto se ejecuta en cada deploy)..."
    if ! update_database; then
        print_warn "Error al actualizar la base de datos. Continuando de todas formas..."
        print_warn "La aplicaci?n se iniciar? pero puede que el esquema no est? actualizado."
    fi
else
    print_warn "La base de datos '${PGDATABASE}' no est? inicializada o no existe."
    print_info "Inicializando base de datos desde cero (primera vez)..."
    if ! init_database; then
        print_error "Error al inicializar la base de datos. Abortando."
        exit 1
    fi
fi

ATTACHMENT_STORAGE_MODE="${ODOO_ATTACHMENT_STORAGE:-db}"
if [ "$ATTACHMENT_STORAGE_MODE" = "s3" ]; then
    print_info "ODOO_ATTACHMENT_STORAGE=s3 detectado: no se fuerza ir_attachment.location=db ni se ejecuta force_storage()."
else
    configure_attachment_storage
    migrate_attachments_to_db
fi

print_info "Base de datos lista. Iniciando Gunicorn..."

# Ejecutar Gunicorn (reemplaza el proceso actual)
# Usar odoo-wsgi:application que tiene la configuraci?n correcta para websockets
# Los logs van a stdout/stderr para PaaS
exec gunicorn odoo-wsgi:application \
    --pythonpath "$SCRIPT_DIR" \
    --config "$SCRIPT_DIR/gunicorn.conf.py" \
    --access-logfile - \
    --error-logfile -

