# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Cliente FCM vía Firebase Admin SDK (HTTP v1 bajo el capó).

Credenciales (precedencia: ruta sobre JSON inline):
- ``ORDER_BRIDGE_FCM_SERVICE_ACCOUNT_PATH``: ruta al JSON de cuenta de servicio.
- ``ORDER_BRIDGE_FCM_SERVICE_ACCOUNT_JSON``: contenido JSON del mismo (p. ej. secret en PaaS).

Ante fallo de ``subscribe_to_topic`` / ``unsubscribe_from_topic`` para un topic concreto, los
llamadores suelen **registrar en log y continuar** (no abortar el POST de registro de token)
— ver controladores.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Iterator
from typing import Any

_logger = logging.getLogger(__name__)

_lock = threading.Lock()

try:
    import firebase_admin
    from firebase_admin import credentials, exceptions, messaging
except ImportError:  # pragma: no cover
    firebase_admin = None
    credentials = None
    exceptions = None
    messaging = None


class FcmConfigurationError(Exception):
    """Falta configuración o el paquete ``firebase_admin`` no está instalado."""


def _load_certificate():
    if not credentials:
        raise FcmConfigurationError('Instale el paquete Python firebase-admin (firebase_admin).')
    path = (os.environ.get('ORDER_BRIDGE_FCM_SERVICE_ACCOUNT_PATH') or '').strip()
    raw = os.environ.get('ORDER_BRIDGE_FCM_SERVICE_ACCOUNT_JSON') or ''
    if path:
        return credentials.Certificate(path)
    if raw.strip():
        return credentials.Certificate(json.loads(raw))
    raise FcmConfigurationError(
        'Defina ORDER_BRIDGE_FCM_SERVICE_ACCOUNT_PATH o ORDER_BRIDGE_FCM_SERVICE_ACCOUNT_JSON'
    )


def ensure_firebase_app():
    """Inicializa la app Firebase una vez por proceso (idempotente)."""
    if messaging is None:
        raise FcmConfigurationError('Instale el paquete Python firebase-admin (firebase_admin).')
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass
    with _lock:
        try:
            firebase_admin.get_app()
            return
        except ValueError:
            try:
                cred = _load_certificate()
            except (OSError, ValueError, TypeError) as e:
                raise FcmConfigurationError('Credenciales FCM no válidas o ilegibles') from e
            firebase_admin.initialize_app(cred)


def subscribe_to_topic(tokens: list[str], topic: str) -> bool:
    """Suscribe ``tokens`` a ``topic``. Devuelve True si no hay fallos notificados."""
    ensure_firebase_app()
    if not tokens:
        return True
    try:
        resp = messaging.subscribe_to_topic(tokens, topic)
    except (exceptions.FirebaseError, Exception) as e:  # pylint: disable=broad-except
        _logger.warning('FCM subscribe_to_topic %r: %s', topic, e, exc_info=True)
        return False
    if resp.failure_count:
        for e in resp.errors or []:
            _logger.warning('FCM subscribe_to_topic %r: %s', topic, e)
        return False
    return True


def unsubscribe_from_topic(tokens: list[str], topic: str) -> bool:
    ensure_firebase_app()
    if not tokens:
        return True
    try:
        resp = messaging.unsubscribe_from_topic(tokens, topic)
    except (exceptions.FirebaseError, Exception) as e:  # pylint: disable=broad-except
        _logger.warning('FCM unsubscribe_from_topic %r: %s', topic, e, exc_info=True)
        return False
    if resp.failure_count:
        for e in resp.errors or []:
            _logger.warning('FCM unsubscribe_from_topic %r: %s', topic, e)
        return False
    return True


def _str_data(data: dict[str, Any] | None) -> dict[str, str] | None:
    if not data:
        return None
    return {str(k): str(v) for k, v in data.items()}


def send_notification_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> list[Any]:
    """Envía la misma notificación a muchos tokens (trozos de 500 en el llamador)."""
    ensure_firebase_app()
    if not tokens:
        return []
    str_data = _str_data(data)
    notification = messaging.Notification(title=title, body=body)
    mm_kwargs: dict[str, Any] = {
        'notification': notification,
        'tokens': tokens,
    }
    if str_data:
        mm_kwargs['data'] = str_data
    multicast = messaging.MulticastMessage(**mm_kwargs)
    return list(messaging.send_each_for_multicast(multicast))


def iter_token_batches(tokens: list[str], batch_size: int = 500) -> Iterator[list[str]]:
    """Trocea una lista de tokens (máx. 500 por petición FCM multicast)."""
    for i in range(0, len(tokens), batch_size):
        yield tokens[i : i + batch_size]


def send_to_topic(
    topic: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> str:
    """Mensaje a un topic (p. ej. campaña global)."""
    ensure_firebase_app()
    str_data = _str_data(data)
    msg_kwargs: dict[str, Any] = {
        'topic': topic,
        'notification': messaging.Notification(title=title, body=body),
    }
    if str_data:
        msg_kwargs['data'] = str_data
    msg = messaging.Message(**msg_kwargs)
    return messaging.send(msg)
