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

# Configurar base de datos desde DATABASE_URL o variables de entorno PostgreSQL estándar
database_url = os.getenv('DATABASE_URL')
if database_url:
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    conf['db_host'] = parsed.hostname or 'localhost'
    conf['db_port'] = parsed.port or 5432
    conf['db_user'] = parsed.username or 'odoo'
    conf['db_password'] = parsed.password or ''
    conf['db_name'] = parsed.path.lstrip('/')
    if parsed.query:
        import urllib.parse as up
        params = dict(up.parse_qsl(parsed.query))
        if 'sslmode' in params:
            conf['db_sslmode'] = params['sslmode']
else:
    if os.getenv('PGDATABASE'):
        conf['db_name'] = os.getenv('PGDATABASE')
    if os.getenv('PGHOST'):
        conf['db_host'] = os.getenv('PGHOST')
    if os.getenv('PGPORT'):
        conf['db_port'] = int(os.getenv('PGPORT'))
    if os.getenv('PGUSER'):
        conf['db_user'] = os.getenv('PGUSER')
    if os.getenv('PGPASSWORD'):
        conf['db_password'] = os.getenv('PGPASSWORD')

# Configurar gevent_port al mismo puerto que http_port para websockets
# Esto es necesario porque Odoo verifica que los websockets vengan del puerto gevent_port
http_port = int(os.getenv('GUNICORN_BIND', '0.0.0.0:8069').split(':')[-1])
conf['gevent_port'] = http_port
conf['http_port'] = http_port

# Path to the Odoo Addons repository (comma-separated for multiple locations)
# Default: './odoo/addons,./addons'
# Uncomment and adjust if needed:
# conf['addons_path'] = './odoo/addons,./addons'

# Other Odoo configuration options
# conf['logfile'] = '/var/log/odoo/odoo.log'
# conf['log_level'] = 'info'

# ----------------------------------------------------------
# WSGI Application Wrapper para Gunicorn con gevent
# ----------------------------------------------------------

# Importar la aplicación de Odoo
from odoo.http import root

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
application = WebSocketMiddleware(root)

# Nota: application.initialize() se llamará automáticamente cuando sea necesario
# Con preload_app=False, cada worker inicializará su propia instancia

