# Gunicorn configuration file
# This file can be used as an alternative to command-line options
# Usage: gunicorn -c gunicorn.conf.py odoo.http:root

import multiprocessing
import os

# Server socket
bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8069')
backlog = 2048

# Worker processes
# Formula: (2 x CPU cores) + 1
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
# Usar gevent para soportar websockets (requerido para /websocket endpoint)
# Usar nuestro worker personalizado que añade soporte para websockets
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gunicorn_gevent_handler.GeventWorkerWithSocket')
worker_connections = int(os.getenv('GUNICORN_WORKER_CONNECTIONS', '1000'))
# Timeout aumentado para entornos serverless que pueden tener timeouts largos
# 600 segundos (10 minutos) es recomendado para websockets en entornos serverless
timeout = int(os.getenv('GUNICORN_TIMEOUT', '600'))
# Keepalive aumentado para mantener conexiones websocket vivas
# 75 segundos ayuda a evitar que proxies cierren conexiones idle
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '75'))

# Restart workers after this many requests, to help prevent memory leaks
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '2000'))
max_requests_jitter = 50

# Process naming
proc_name = 'odoo'

# Logging
# Por defecto usar stdout/stderr para que los logs sean visibles en contenedores
# Se puede sobrescribir con variables de entorno
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # '-' significa stdout
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')     # '-' significa stderr
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Configurar logging para suprimir errores esperados de websockets
import logging
import sys

class WebSocketErrorFilter(logging.Filter):
    """Filter to suppress expected EBADF errors after WebSocket upgrades."""
    def filter(self, record):
        if 'Socket error processing request' in str(record.getMessage()):
            if record.exc_info:
                exc = record.exc_info[1]
                if isinstance(exc, OSError) and getattr(exc, 'errno', None) == 9:
                    return False  # Suppress entirely
        return True

# Aplicar el filtro al logger de errores de Gunicorn
gunicorn_error_logger = logging.getLogger('gunicorn.error')
gunicorn_error_logger.addFilter(WebSocketErrorFilter())

# Process management
daemon = False
# Use /tmp for pidfile to avoid permission issues in PaaS/container environments
pidfile = os.getenv('GUNICORN_PIDFILE', '/tmp/gunicorn.pid')
umask = 0o007
user = os.getenv('GUNICORN_USER', None)
group = os.getenv('GUNICORN_GROUP', None)
tmp_upload_dir = None

# SSL (uncomment if using HTTPS)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Server mechanics
# preload_app debe ser False con gevent para websockets
# Gunicorn maneja automáticamente el monkey patching de gevent cuando worker_class='gevent'
preload_app = os.getenv('GUNICORN_PRELOAD_APP', 'False').lower() == 'true'
reload = False

# Graceful timeout for worker restart
graceful_timeout = 30

# Worker timeout - use /tmp for better compatibility in container/PaaS environments
# /dev/shm requires specific kernel capabilities that may not be available everywhere
worker_tmp_dir = '/tmp'

# Hook para añadir el socket al environ cuando se usa gevent (necesario para websockets)
def on_reload(server):
    """Hook llamado cuando se recarga el servidor"""
    pass

def when_ready(server):
    """Hook llamado cuando el servidor está listo"""
    pass

def worker_int(worker):
    """Hook llamado cuando un worker recibe SIGINT o SIGQUIT"""
    pass

def pre_fork(server, worker):
    """Hook llamado antes de hacer fork del worker"""
    pass

def post_fork(server, worker):
    """Hook llamado después de hacer fork del worker"""
    pass

def _patch_fsspec_sync_for_gevent():
    """fsspec/gevent: drop sync()'s false-positive running-loop check.

    Under monkey.patch_all() fsspec's IO loop runs in a greenlet on the same
    OS thread as the calling greenlet, so asyncio (per-OS-thread, C level)
    reports it as the running loop. The calling greenlet is not actually
    inside the loop's iteration; threading.Event.wait() is gevent-patched and
    yields cooperatively, so the IO-loop greenlet processes the submitted
    coroutine and signals back. See fsspec/filesystem_spec#1701.
    """
    import asyncio
    import threading
    import fsspec.asyn as _asyn

    def sync_no_running_loop_check(loop, func, *args, timeout=None, **kwargs):
        timeout = timeout if timeout else None
        if loop is None or loop.is_closed():
            raise RuntimeError("Loop is not running")
        coro = func(*args, **kwargs)
        result = [None]
        event = threading.Event()
        asyncio.run_coroutine_threadsafe(
            _asyn._runner(event, coro, result, timeout), loop
        )
        while True:
            if event.wait(1):
                break
            if timeout is not None:
                timeout -= 1
                if timeout < 0:
                    raise _asyn.FSTimeoutError
        rr = result[0]
        if isinstance(rr, asyncio.TimeoutError):
            raise _asyn.FSTimeoutError from rr
        if isinstance(rr, BaseException):
            raise rr
        return rr

    _asyn.sync = sync_no_running_loop_check


def post_worker_init(worker):
    """Hook llamado después de que el worker inicializa la aplicación"""
    if issubclass(worker.__class__, __import__("gunicorn.workers.ggevent", fromlist=["GeventWorker"]).GeventWorker):
        _patch_fsspec_sync_for_gevent()

def worker_abort(worker):
    """Hook llamado cuando un worker recibe SIGABRT"""
    pass

