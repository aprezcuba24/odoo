# Dockerfile para la aplicación Odoo
FROM python:3.12-slim

# Variables de entorno
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema necesarias para Odoo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    libsass-dev \
    libldap2-dev \
    libsasl2-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    python3-dev \
    fontconfig \
    xfonts-75dpi \
    xfonts-base \
    xvfb \
    libxrender1 \
    libxext6 \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Instalar Wkhtmltopdf - intentar primero desde repositorios, luego desde paquete Bookworm
RUN apt-get update && \
    (apt-get install -y --no-install-recommends wkhtmltopdf 2>/dev/null || \
     (curl -L https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb -o /tmp/wkhtmltopdf.deb && \
      apt-get install -y --no-install-recommends /tmp/wkhtmltopdf.deb || \
      (dpkg -i /tmp/wkhtmltopdf.deb || apt-get install -yf) && \
      rm -f /tmp/wkhtmltopdf.deb)) && \
    rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para desarrollo
RUN useradd -m -s /bin/bash odoo && \
    mkdir -p /app && \
    chown -R odoo:odoo /app

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos primero (para aprovechar cache de Docker)
COPY --chown=odoo:odoo requirements.txt /app/

# Instalar dependencias de Python (como root para poder instalar paquetes)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar el resto del código con permisos correctos
COPY --chown=odoo:odoo . /app/

# Cambiar al usuario no-root
USER odoo

# Exponer el puerto por defecto de Odoo
EXPOSE 8069

# Comando por defecto (puede ser sobrescrito en docker-compose)
CMD ["python3", "odoo-bin", "--dev=all"]

