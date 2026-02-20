#!/bin/sh
# deploy.sh — One-time VPS setup script for Odoo 19.0 (no Docker)
# Assumes app code is already at /apps/odoo
# Run as root: sudo bash deploy.sh OR: sudo sh deploy.sh (auto-switches to bash)
[ -n "$BASH_VERSION" ] || exec bash "$0" "$@"
set -euo pipefail

APP_DIR="/apps/odoo"
VENV_DIR="${APP_DIR}/venv"
LOG_DIR="/var/log/odoo"
RUN_DIR="/var/run/odoo"
SERVICE_SRC="$(dirname "$(realpath "$0")")/odoo.service"
SERVICE_DEST="/etc/systemd/system/odoo.service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Must run as root
if [[ $EUID -ne 0 ]]; then
    error "Este script debe ejecutarse como root: sudo bash deploy.sh"
fi

# App directory must exist
if [[ ! -d "$APP_DIR" ]]; then
    error "El directorio de la aplicación ${APP_DIR} no existe. Clona el código antes de ejecutar este script."
fi

# ─── Section 1: System packages ───────────────────────────────────────────────
info "Instalando paquetes del sistema..."
apt-get update -qq
apt-get install -y --no-install-recommends \
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
    xvfb \
    libxrender1 \
    libxext6 \
    libssl-dev \
    curl \
    git \
    software-properties-common
rm -rf /var/lib/apt/lists/*

# ─── Section 2: Python 3.12 ───────────────────────────────────────────────────
info "Instalando Python 3.12..."
if ! python3.12 --version &>/dev/null; then
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y --no-install-recommends python3.12 python3.12-venv python3.12-dev
    rm -rf /var/lib/apt/lists/*
else
    info "Python 3.12 ya está instalado: $(python3.12 --version)"
fi

# ─── Section 3: wkhtmltopdf ───────────────────────────────────────────────────
info "Instalando wkhtmltopdf..."
if ! command -v wkhtmltopdf &>/dev/null; then
    WKHTML_DEB="/tmp/wkhtmltopdf.deb"
    curl -sSL \
        "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb" \
        -o "$WKHTML_DEB"
    apt-get update -qq
    dpkg -i "$WKHTML_DEB" || apt-get install -yf
    rm -f "$WKHTML_DEB"
    rm -rf /var/lib/apt/lists/*
else
    info "wkhtmltopdf ya está instalado: $(wkhtmltopdf --version 2>&1 | head -1)"
fi

# ─── Section 4: odoo user and directories ─────────────────────────────────────
info "Creando usuario 'odoo' y directorios..."
if ! id -u odoo &>/dev/null; then
    useradd -m -s /bin/bash -u 1000 odoo
    info "Usuario 'odoo' creado."
else
    info "Usuario 'odoo' ya existe."
fi
mkdir -p "$LOG_DIR" "$RUN_DIR"
chown odoo:odoo "$LOG_DIR" "$RUN_DIR"

# ─── Section 5: Set ownership and permissions ─────────────────────────────────
chmod +x "${APP_DIR}/docker-entrypoint.sh" 2>/dev/null || true
info "Estableciendo permisos de propiedad en ${APP_DIR}..."
chown -R odoo:odoo "$APP_DIR" "$LOG_DIR" "$RUN_DIR"

# ─── Section 6: Python virtualenv and dependencies ────────────────────────────
info "Creando virtualenv en ${VENV_DIR}..."
if [[ ! -d "$VENV_DIR" ]]; then
    python3.12 -m venv "$VENV_DIR"
fi

info "Instalando dependencias de Python..."
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
"${VENV_DIR}/bin/pip" install "gunicorn[gevent]"

# Fix virtualenv ownership so odoo user can use it
chown -R odoo:odoo "$VENV_DIR"

# ─── Section 7: .env file ─────────────────────────────────────────────────────
ENV_FILE="${APP_DIR}/.env"
ENV_EXAMPLE="${APP_DIR}/.env.example"

if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
        info "Creando ${ENV_FILE} desde .env.example..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        info "Creando ${ENV_FILE} con valores de plantilla..."
        cat > "$ENV_FILE" <<'EOF'
# Odoo environment configuration
# Edit this file before starting the service

# ── Database connection (required) ──────────────────────────────────────────
# Full PostgreSQL connection URI (recommended):
DATABASE_URL=postgresql://user:password@host:5432/dbname

# ── Gunicorn (required for direct IP access) ─────────────────────────────────
GUNICORN_BIND=0.0.0.0:8069
GUNICORN_WORKERS=4
GUNICORN_WORKER_CLASS=gunicorn_gevent_handler.GeventWorkerWithSocket
GUNICORN_TIMEOUT=600
GUNICORN_KEEPALIVE=75
GUNICORN_LOG_LEVEL=info
GUNICORN_ACCESS_LOG=-
GUNICORN_ERROR_LOG=-

# ── Odoo DB initialization (first run only) ──────────────────────────────────
DB_LANGUAGE=es_ES
DB_USERNAME=admin
DB_PASSWORD_ADMIN=changeme
DB_WITH_DEMO=false
EOF
    fi
    chown odoo:odoo "$ENV_FILE"
    chmod 640 "$ENV_FILE"
fi

echo ""
warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
warn "ACCIÓN REQUERIDA: Edita ${ENV_FILE} antes de continuar."
warn "  • Establece DATABASE_URL con tu conexión PostgreSQL real."
warn "  • Asegúrate de que GUNICORN_BIND=0.0.0.0:8069 esté presente."
warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -rp "¿Ya configuraste DATABASE_URL en ${ENV_FILE}? (s/N): " confirm
if [[ ! "$confirm" =~ ^[sS]$ ]]; then
    warn "Edita el archivo y vuelve a ejecutar el script, o continúa manualmente:"
    warn "  sudo nano ${ENV_FILE}"
    warn "  sudo systemctl start odoo"
    # Still install the service so it's ready when the user edits the env file
fi

# ─── Section 8: Install systemd service ───────────────────────────────────────
info "Instalando servicio systemd..."
if [[ -f "$SERVICE_SRC" ]]; then
    cp "$SERVICE_SRC" "$SERVICE_DEST"
    systemctl daemon-reload
    systemctl enable odoo
    if [[ "$confirm" =~ ^[sS]$ ]]; then
        systemctl restart odoo
        info "Servicio 'odoo' iniciado."
    else
        warn "Servicio instalado y habilitado, pero NO iniciado (DATABASE_URL no confirmada)."
        warn "Cuando estés listo: sudo systemctl start odoo"
    fi
else
    error "No se encontró odoo.service en $(dirname "$SERVICE_SRC"). Asegúrate de que el archivo esté junto a deploy.sh."
fi

# ─── Section 9: Open firewall port ────────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    info "Abriendo puerto 8069 en ufw..."
    ufw allow 8069/tcp
elif command -v iptables &>/dev/null; then
    if ! iptables -C INPUT -p tcp --dport 8069 -j ACCEPT &>/dev/null; then
        info "Abriendo puerto 8069 en iptables..."
        iptables -I INPUT -p tcp --dport 8069 -j ACCEPT
        info "Nota: esta regla de iptables no persiste tras reinicio. Instala iptables-persistent si lo necesitas."
    else
        info "Puerto 8069 ya está abierto en iptables."
    fi
else
    warn "No se detectó ufw ni iptables. Asegúrate de que el puerto 8069 sea accesible desde internet."
fi
warn "Si usas un proveedor cloud (AWS, GCP, DigitalOcean, etc.), verifica también el firewall/security group del proveedor."

echo ""
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Despliegue completado. Próximos pasos:"
info "  1. sudo systemctl status odoo"
info "  2. sudo journalctl -u odoo -f"
info "  3. curl http://localhost:8069/web/health"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
