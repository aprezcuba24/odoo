"""
Custom Gunicorn handler para gevent que añade el socket al environ.
Esto es necesario para que Odoo pueda manejar conexiones websocket.
"""

from gunicorn.workers.ggevent import GeventWorker, PyWSGIHandler
import logging

_logger = logging.getLogger(__name__)


class GeventWSGIHandler(PyWSGIHandler):
    """
    Handler personalizado que añade el socket al environ para websockets.
    Extiende el handler de gevent de Gunicorn para añadir la funcionalidad
    que Odoo necesita.
    """

    def __init__(self, *args, **kwargs):
        """Inicializar el handler y asegurar que tenemos acceso al socket"""
        super().__init__(*args, **kwargs)
        # El socket debería estar disponible después de la inicialización
    
    def get_environ(self):
        """Añadir el socket al environ para que Odoo pueda usarlo con websockets"""
        environ = super().get_environ()
        
        # Añadir el socket al environ (necesario para websockets de Odoo)
        # En gevent.pywsgi, el socket está disponible como self.socket
        # que es el objeto socket del cliente conectado
        socket_obj = None
        
        # Intentar obtener el socket de diferentes formas
        # El socket es el objeto de conexión TCP del cliente
        if hasattr(self, 'socket') and self.socket is not None:
            socket_obj = self.socket
            _logger.debug("Socket obtenido de self.socket")
        elif hasattr(self, 'connection') and self.connection is not None:
            socket_obj = self.connection
            _logger.debug("Socket obtenido de self.connection")
        elif hasattr(self, 'client') and self.client is not None:
            # En algunas versiones, el socket puede estar en client
            socket_obj = self.client
            _logger.debug("Socket obtenido de self.client")
        
        # Si encontramos el socket, añadirlo al environ
        # Esto es crítico para que Odoo pueda manejar websockets
        if socket_obj is not None:
            environ['socket'] = socket_obj
            _logger.debug("Socket añadido al environ para websockets")
        else:
            # Si no encontramos el socket, registrar un error
            # Esto ayudará a diagnosticar el problema
            _logger.error(
                "No se pudo obtener el socket del handler. "
                "Atributos disponibles: %s",
                [attr for attr in dir(self) if not attr.startswith('_')]
            )
        
        # Manejar upgrade a websocket (similar al ProxyHandler de Odoo)
        if self._connection_upgrade_requested():
            # Asegurar que usamos HTTP/1.1 para websockets
            self.protocol_version = "HTTP/1.1"
            # Deshabilitar chunked encoding para websockets
            if hasattr(self, 'response_use_chunked'):
                self.response_use_chunked = False
            # Deshabilitar soporte para HTTP chunking en reads
            environ['wsgi.input'] = self.rfile
            environ['wsgi.input_terminated'] = False
        
        return environ

    def _connection_upgrade_requested(self):
        """Verificar si se está solicitando un upgrade a websocket"""
        if self.headers.get('Connection', '').lower() == 'upgrade':
            return True
        if self.headers.get('Upgrade', '').lower() == 'websocket':
            return True
        return False

    def send_header(self, keyword, value):
        """Prevenir Connection: close en websockets"""
        # Prevenir `Connection: close` header en websockets (incompatible con websockets)
        if self._connection_upgrade_requested() and keyword == 'Connection' and value == 'close':
            # No cerrar la conexión, pero marcar que no debemos procesar más requests
            # El websocket se encargará de la conexión
            return
        super().send_header(keyword, value)

    def finalize_headers(self):
        """Finalizar headers, deshabilitando chunked encoding para websockets"""
        super().finalize_headers()
        # Deshabilitar chunked writes cuando se hace upgrade a websocket
        if self.code == 101:  # Switching Protocols
            if hasattr(self, 'response_use_chunked'):
                self.response_use_chunked = False
            # Prevenir que Gunicorn intente leer más datos después del upgrade
            # Similar a lo que hace Odoo en RequestHandler.end_headers()
            if self._connection_upgrade_requested():
                from io import BytesIO
                # Reemplazar rfile/wfile para evitar que Werkzeug/Gunicorn cierre la conexión
                # Esto es necesario para websockets (ver odoo/service/server.py línea 208-210)
                # Esto previene que Gunicorn intente leer más datos del socket
                # después de que Odoo tome control del socket para el websocket
                self.rfile = BytesIO()
                self.wfile = BytesIO()
                # Marcar que la conexión debe cerrarse después de enviar la respuesta
                # Esto previene que Gunicorn intente leer más requests del mismo socket
                # Odoo tiene su propia referencia al socket en environ['socket'] y lo manejará
                self.close_connection = True
                # Almacenar una referencia al socket para cerrarlo después
                # si está disponible
                if hasattr(self, 'socket') and self.socket:
                    self._websocket_socket = self.socket
    
    def finish(self):
        """Finalizar la respuesta, cerrando el socket si fue un upgrade a websocket"""
        try:
            super().finish()
        finally:
            # Si fue un upgrade a websocket, cerrar el socket después de enviar la respuesta
            # para evitar que Gunicorn intente leer más requests
            if hasattr(self, '_websocket_socket') and self.code == 101:
                _logger.debug("Cerrando socket después de upgrade a websocket")
                try:
                    # Cerrar el socket desde la perspectiva de Gunicorn
                    # Odoo tiene su propia referencia y lo manejará
                    if hasattr(self, 'socket') and self.socket:
                        # No cerrar realmente el socket, solo marcar que no debe leerse más
                        # El socket se pasará a Odoo a través del environ
                        pass
                except Exception as e:
                    _logger.debug(f"Error al manejar socket después de upgrade: {e}")


class GeventWorkerWithSocket(GeventWorker):
    """
    Worker de gevent personalizado que usa nuestro handler personalizado.
    Modificado para manejar correctamente los websockets.
    """
    wsgi_handler = GeventWSGIHandler
    
    def handle(self, listener, client, addr):
        """
        Manejar una conexión, manejando correctamente los upgrades a websocket.
        Después de un upgrade, el socket es tomado por Odoo y cualquier intento
        de leer más datos resultará en "Bad file descriptor", lo cual es esperado.
        """
        try:
            # Usar el método padre que maneja requests normalmente
            return super().handle(listener, client, addr)
        except (OSError, IOError) as e:
            # Después de un upgrade a websocket, Odoo toma el socket y
            # cualquier intento de leer más datos del socket resultará en
            # "Bad file descriptor". Esto es esperado y no es un error real.
            errno = getattr(e, 'errno', None)
            if errno == 9:  # EBADF - Bad file descriptor
                # Este error es esperado después de un upgrade a websocket
                # El socket ha sido tomado por Odoo para manejar el websocket
                _logger.debug("Socket tomado por websocket después de upgrade, ignorando error esperado")
                return
            # Para otros errores, re-lanzar
            raise
        except Exception as e:
            # Capturar cualquier otro error relacionado con el socket
            # que pueda ocurrir después de un upgrade
            errno = getattr(e, 'errno', None)
            if errno == 9:  # EBADF - Bad file descriptor
                _logger.debug("Error de socket después de upgrade, ignorando")
                return
            raise

