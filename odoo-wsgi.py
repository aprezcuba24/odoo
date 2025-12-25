# WSGI Handler configuration file for Gunicorn
#
# This file configures Odoo to run with Gunicorn in production.
# Adjust the settings below according to your environment.
#
# Usage:
#   $ gunicorn odoo.http:root --pythonpath . -c odoo-wsgi.py
#
# Or with systemd:
#   $ systemctl start odoo-gunicorn

from odoo.http import root as application
from odoo.tools import config as conf
import os

# ----------------------------------------------------------
# Common Configuration
# ----------------------------------------------------------

# Path to the Odoo Addons repository (comma-separated for multiple locations)
# Default: './odoo/addons,./addons'
# Uncomment and adjust if needed:
# conf['addons_path'] = './odoo/addons,./addons'

# Optional database config if not using local socket
# Uncomment and adjust if needed:
# conf['db_name'] = 'odoo'
# conf['db_host'] = 'localhost'
# conf['db_user'] = 'odoo'
# conf['db_port'] = 5432
# conf['db_password'] = 'your_password'

# Other Odoo configuration options
# conf['http_port'] = 8069
# conf['logfile'] = '/var/log/odoo/odoo.log'
# conf['log_level'] = 'info'

# ----------------------------------------------------------
# Initializing the server
# ----------------------------------------------------------

application.initialize()

# ----------------------------------------------------------
# Gunicorn Configuration
# ----------------------------------------------------------

# Server socket
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:8069')
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', '4'))
worker_class = 'sync'
worker_connections = 1000
timeout = int(os.getenv('GUNICORN_TIMEOUT', '240'))
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '2000'))
max_requests_jitter = 50

# Process naming
proc_name = 'odoo'

# Logging
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # '-' means stdout
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')    # '-' means stderr
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process management
daemon = False
pidfile = os.getenv('GUNICORN_PIDFILE', '/var/run/odoo/gunicorn.pid')
umask = 0o007
user = os.getenv('GUNICORN_USER', None)
group = os.getenv('GUNICORN_GROUP', None)
tmp_upload_dir = None

# SSL (if needed)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Server mechanics
preload_app = True
reload = False

