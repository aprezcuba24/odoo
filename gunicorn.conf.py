# Gunicorn configuration file
# This file can be used as an alternative to command-line options
# Usage: gunicorn -c gunicorn.conf.py odoo.http:root

import multiprocessing
import os

# Server socket
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:8069')
backlog = 2048

# Worker processes
# Formula: (2 x CPU cores) + 1
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
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
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '/var/log/odoo/gunicorn-access.log')
errorlog = os.getenv('GUNICORN_ERROR_LOG', '/var/log/odoo/gunicorn-error.log')
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process management
daemon = False
pidfile = os.getenv('GUNICORN_PIDFILE', '/var/run/odoo/gunicorn.pid')
umask = 0o007
user = os.getenv('GUNICORN_USER', None)
group = os.getenv('GUNICORN_GROUP', None)
tmp_upload_dir = None

# SSL (uncomment if using HTTPS)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Server mechanics
preload_app = True
reload = False

# Graceful timeout for worker restart
graceful_timeout = 30

# Worker timeout
worker_tmp_dir = '/dev/shm'  # Use shared memory for better performance (Linux)

