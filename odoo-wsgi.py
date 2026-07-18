# WSGI Handler configuration file for Gunicorn
#
# This file configures Odoo to run with Gunicorn in production on PaaS platforms.
# Adjust the settings below according to your environment.
#
# Usage:
#   $ gunicorn odoo-wsgi:application --pythonpath . -c gunicorn.conf.py

import os
from odoo.tools import config as conf

# ----------------------------------------------------------
# Common Configuration
# ----------------------------------------------------------


def _env_truthy(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


MULTI_TENANT = _env_truthy('ODOO_MULTI_TENANT')

# Configurar base de datos desde DATABASE_URL o variables de entorno PostgreSQL estándar
database_url = os.getenv('DATABASE_URL')
if database_url:
    from urllib.parse import urlparse
    import urllib.parse as up

    parsed = urlparse(database_url)
    conf['db_host'] = parsed.hostname or 'localhost'
    conf['db_port'] = parsed.port or 5432
    conf['db_user'] = parsed.username or 'odoo'
    conf['db_password'] = parsed.password or ''
    if parsed.query:
        params = dict(up.parse_qsl(parsed.query))
        if 'sslmode' in params:
            conf['db_sslmode'] = params['sslmode']
    if MULTI_TENANT:
        # Multi-tenant: route DBs by hostname (dbfilter); do not pin db_name.
        conf['db_name'] = []
    else:
        conf['db_name'] = parsed.path.lstrip('/')
else:
    if os.getenv('PGHOST'):
        conf['db_host'] = os.getenv('PGHOST')
    if os.getenv('PGPORT'):
        conf['db_port'] = int(os.getenv('PGPORT'))
    if os.getenv('PGUSER'):
        conf['db_user'] = os.getenv('PGUSER')
    if os.getenv('PGPASSWORD'):
        conf['db_password'] = os.getenv('PGPASSWORD')
    if MULTI_TENANT:
        conf['db_name'] = []
    elif os.getenv('PGDATABASE'):
        conf['db_name'] = os.getenv('PGDATABASE')

if MULTI_TENANT:
    conf['dbfilter'] = os.getenv('ODOO_DBFILTER', r'^%d$')
    conf['list_db'] = _env_truthy('ODOO_LIST_DB', default=False)
    conf['proxy_mode'] = _env_truthy('ODOO_PROXY_MODE', default=True)
    # Load tenant_routing (domain map + /tenant/provision UI) as server-wide.
    wide = list(conf.get('server_wide_modules') or [])
    if not wide:
        wide = ['base', 'rpc', 'web']
    if 'tenant_routing' not in wide:
        wide.append('tenant_routing')
    conf['server_wide_modules'] = wide
elif _env_truthy('ODOO_PROXY_MODE'):
    conf['proxy_mode'] = True

admin_passwd = os.getenv('DB_PASSWORD_ADMIN')
if admin_passwd:
    conf['admin_passwd'] = admin_passwd

# Configurar gevent_port al mismo puerto que http_port para websockets
# Esto es necesario porque Odoo verifica que los websockets vengan del puerto gevent_port
http_port = int(os.getenv('GUNICORN_BIND', '0.0.0.0:8069').split(':')[-1])
conf['gevent_port'] = http_port
conf['http_port'] = http_port

# Ensure own_modules (tenant_routing, etc.) are on the addons path for Gunicorn.
# docker-entrypoint.sh exports ODOO_ADDONS_PATH; apply it explicitly before initialize().
addons_path_env = os.getenv('ODOO_ADDONS_PATH', '').strip()
if addons_path_env:
    conf['addons_path'] = addons_path_env

# ----------------------------------------------------------
# WSGI Application Wrapper para Gunicorn con gevent
# ----------------------------------------------------------

import logging

from odoo.http import root

_logger = logging.getLogger(__name__)

# Required for Gunicorn: load server-wide modules (web, tenant_routing, …)
# so nodb routes (/web/health, /tenant/provision) and ODOO_TENANT_DOMAIN_MAP work.
# See setup/odoo-wsgi.example.py — this is not automatic under Gunicorn.
root.initialize()

_logger.info(
    'odoo-wsgi ready: MULTI_TENANT=%s dbfilter=%r server_wide_modules=%s',
    MULTI_TENANT,
    conf.get('dbfilter') or '',
    conf.get('server_wide_modules'),
)


class WebSocketMiddleware:
    """
    Middleware WSGI que asegura que el socket esté en el environ.
    Esto es un respaldo en caso de que el handler personalizado no funcione.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Asegurar que el socket esté en el environ
        # El handler personalizado debería haberlo añadido, pero esto es un respaldo
        if 'socket' not in environ:
            # Intentar obtener el socket del connection si está disponible
            # En algunos casos, el socket puede estar en el connection del servidor
            try:
                # El socket puede estar disponible a través del servidor
                if 'gunicorn.socket' in environ:
                    environ['socket'] = environ['gunicorn.socket']
                # O puede estar en el connection del request
                elif hasattr(environ.get('gunicorn.socket'), 'socket'):
                    environ['socket'] = environ['gunicorn.socket'].socket
            except Exception:
                # Si no podemos obtener el socket, continuar sin él
                # Esto causará un error en websockets, pero las requests HTTP funcionarán
                pass

        return self.app(environ, start_response)


# Crear la aplicación envuelta con el middleware
# El handler personalizado de Gunicorn (gunicorn_gevent_handler.py) debería
# añadir el socket al environ, pero el middleware actúa como respaldo
# Con preload_app=False, cada worker importa este módulo e inicializa su propia instancia
application = WebSocketMiddleware(root)
