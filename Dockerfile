# Dockerfile para la aplicación Odoo en producción
# Imagen optimizada para ejecutarse con PostgreSQL externo
FROM python:3.12-slim

# Variables de entorno del sistema
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Variables de entorno de Gunicorn (pueden ser sobrescritas)
ENV GUNICORN_BIND=0.0.0.0:8069 \
    GUNICORN_WORKERS=4 \
    GUNICORN_TIMEOUT=240 \
    GUNICORN_MAX_REQUESTS=2000 \
    GUNICORN_MAX_REQUESTS_JITTER=50 \
    GUNICORN_LOG_LEVEL=info \
    GUNICORN_ACCESS_LOG=/var/log/odoo/gunicorn-access.log \
    GUNICORN_ERROR_LOG=/var/log/odoo/gunicorn-error.log

# Variables de entorno de Odoo (deben ser configuradas al ejecutar el contenedor)
# Variables requeridas para conexión a PostgreSQL (estándar de PostgreSQL):
# - PGHOST: hostname del servidor PostgreSQL (requerido)
# - PGPORT: puerto (por defecto 5432)
# - PGUSER: usuario de la base de datos (requerido)
# - PGPASSWORD: contraseña de la base de datos (requerido)
# - PGDATABASE: nombre de la base de datos (requerido)
# Variables opcionales para inicialización:
# - DB_LANGUAGE: idioma por defecto (por defecto 'es_ES')
# - DB_USERNAME: nombre de usuario admin (por defecto 'admin')
# - DB_PASSWORD_ADMIN: contraseña del usuario admin (por defecto 'admin')
# - DB_WITH_DEMO: instalar datos de demostración ('true' o 'false', por defecto 'false')
# Ejemplo: docker run -e PGHOST=postgres.example.com -e PGDATABASE=odoo -e PGUSER=odoo -e PGPASSWORD=password ...

# Instalar dependencias del sistema necesarias para Odoo
# Agrupadas para optimizar el caché de Docker
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Herramientas de compilación y desarrollo
    build-essential \
    python3-dev \
    # Cliente PostgreSQL (necesario para psycopg2, pero no instalamos el servidor)
    libpq-dev \
    # Dependencias para procesamiento de imágenes
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    # Dependencias XML/XSLT
    libxml2-dev \
    libxslt1-dev \
    # Dependencias para SASS
    libsass-dev \
    # Dependencias para LDAP
    libldap2-dev \
    libsasl2-dev \
    # Dependencias para Wkhtmltopdf
    fontconfig \
    xfonts-75dpi \
    xfonts-base \
    xvfb \
    libxrender1 \
    libxext6 \
    # SSL/TLS
    libssl3 \
    # Utilidades
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar Wkhtmltopdf para generación de PDFs
# Intentar desde repositorios, luego desde paquete oficial
RUN apt-get update && \
    (apt-get install -y --no-install-recommends wkhtmltopdf 2>/dev/null || \
     (curl -L https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb -o /tmp/wkhtmltopdf.deb && \
      apt-get install -y --no-install-recommends /tmp/wkhtmltopdf.deb || \
      (dpkg -i /tmp/wkhtmltopdf.deb || apt-get install -yf) && \
      rm -f /tmp/wkhtmltopdf.deb)) && \
    rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para producción (mejores prácticas de seguridad)
RUN useradd -m -s /bin/bash -u 1000 odoo && \
    mkdir -p /app /var/log/odoo /var/run/odoo && \
    chown -R odoo:odoo /app /var/log/odoo /var/run/odoo

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos primero (para aprovechar cache de Docker)
COPY --chown=odoo:odoo requirements.txt /app/

# Instalar dependencias de Python
# Se instala como root primero, luego se cambia al usuario odoo
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    pip install gunicorn

# Copiar el resto del código de la aplicación
COPY --chown=odoo:odoo . /app/

# Asegurar que los scripts ejecutables tengan permisos correctos
RUN chmod +x /app/odoo-bin && \
    if [ -f /app/docker-entrypoint.sh ]; then chmod +x /app/docker-entrypoint.sh; fi

# Cambiar al usuario no-root (seguridad)
USER odoo

# Exponer el puerto por defecto de Odoo
EXPOSE 8069

# Healthcheck para verificar que el servicio está funcionando
# Verifica que el endpoint de salud responda correctamente
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8069/web/health', timeout=5).read()" || exit 1

# Script de entrada que inicializa/actualiza la base de datos antes de iniciar Gunicorn
# El script verifica si la base de datos existe:
# - Si no existe o no está inicializada: la crea e inicializa desde cero (odoo-bin db init)
# - Si existe: actualiza todos los módulos (odoo-bin module upgrade base)
# Luego inicia Gunicorn para servir la aplicación
ENTRYPOINT ["/app/docker-entrypoint.sh"]

