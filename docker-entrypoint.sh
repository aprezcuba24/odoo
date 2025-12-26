#!/bin/bash
# Script de entrada para Docker - Inicializa/actualiza la base de datos y luego inicia Gunicorn
set -e

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

# Verificar que las variables de entorno de base de datos estén configuradas
if [ -z "$PGDATABASE" ]; then
    print_error "PGDATABASE no está configurada. Por favor, configura las variables de entorno de la base de datos."
    exit 1
fi

if [ -z "$PGHOST" ]; then
    print_error "PGHOST no está configurada. Por favor, configura las variables de entorno de la base de datos."
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

# Función para verificar si la base de datos está inicializada
check_database_initialized() {
    print_info "Verificando si la base de datos '${PGDATABASE}' está inicializada..."

    # Usar Python para verificar si existe la tabla ir_module_module
    python3 << EOF
import psycopg2
import sys
import os

try:
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=int(os.environ.get('PGPORT', '5432')),
        database=os.environ.get('PGDATABASE'),
        user=os.environ.get('PGUSER', 'odoo'),
        password=os.environ.get('PGPASSWORD', '')
    )
    cur = conn.cursor()
    # Verificar si existe la tabla ir_module_module (indica que Odoo está inicializado)
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

# Función para inicializar la base de datos
init_database() {
    print_info "Inicializando base de datos '${PGDATABASE}' desde cero..."

    # Parámetros adicionales para inicialización
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

    # Ejecutar inicialización
    print_info "Ejecutando: odoo-bin db init ${PGDATABASE} con argumentos de conexión..."
    if /app/odoo-bin db init "${PGDATABASE}" "${INIT_ARGS[@]}" --force; then
        print_info "Base de datos '${PGDATABASE}' inicializada correctamente."
        return 0
    else
        print_error "Error al inicializar la base de datos '${PGDATABASE}'."
        return 1
    fi
}

# Función para actualizar todos los módulos
update_database() {
    print_info "Actualizando esquema de la base de datos '${PGDATABASE}'..."

    # Actualizar todos los módulos (base actualiza todo)
    print_info "Ejecutando: odoo-bin module upgrade base..."
    if /app/odoo-bin module upgrade base; then
        print_info "Base de datos '${PGDATABASE}' actualizada correctamente."
        return 0
    else
        print_error "Error al actualizar la base de datos '${PGDATABASE}'."
        return 1
    fi
}

# Proceso principal
print_info "Iniciando proceso de inicialización/actualización de base de datos..."

# Verificar si la base de datos está inicializada
if check_database_initialized 2>/dev/null; then
    print_info "La base de datos '${PGDATABASE}' ya existe y está inicializada."
    print_info "Actualizando esquema de la base de datos (esto se ejecuta en cada deploy)..."
    if ! update_database; then
        print_warn "Error al actualizar la base de datos. Continuando de todas formas..."
        print_warn "La aplicación se iniciará pero puede que el esquema no esté actualizado."
    fi
else
    print_warn "La base de datos '${PGDATABASE}' no está inicializada o no existe."
    print_info "Inicializando base de datos desde cero (primera vez)..."
    if ! init_database; then
        print_error "Error al inicializar la base de datos. Abortando."
        exit 1
    fi
fi

print_info "Base de datos lista. Iniciando Gunicorn..."

# Ejecutar Gunicorn (reemplaza el proceso actual)
# Usar odoo-wsgi:application que tiene la configuración correcta para websockets
# Los logs van a stdout/stderr para que Railway pueda verlos
exec gunicorn odoo-wsgi:application \
    --pythonpath /app \
    --config /app/gunicorn.conf.py \
    --access-logfile - \
    --error-logfile -

