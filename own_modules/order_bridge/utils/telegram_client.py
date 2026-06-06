# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Cliente Telegram Bot API para notificaciones de pedidos Tienda Apk.

Variables de entorno:
- ``TELEGRAM_BOT_TOKEN``: token del bot.
- ``TELEGRAM_CHAT_ID``: id del chat destino (puede ser negativo en grupos).

Utilidades de formato Markdown legacy: ``escape_markdown``, ``format_money``, ``format_qty``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request

from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

_config_warned = False

_PARSE_MODE = 'Markdown'
_API_URL = 'https://api.telegram.org/bot{token}/sendMessage'
_MARKDOWN_ESCAPE_RE = re.compile(r'([_*`\[])')


def escape_markdown(text: str) -> str:
    """Escapa caracteres reservados del modo Markdown legacy de Telegram."""
    if not text:
        return ''
    return _MARKDOWN_ESCAPE_RE.sub(r'\\\1', str(text))


def format_money(order, amount: float) -> str:
    return escape_markdown(formatLang(order.env, amount, currency_obj=order.currency_id))


def format_qty(order, qty: float) -> str:
    return escape_markdown(formatLang(order.env, qty, digits=0, grouping=False))


def _get_config() -> tuple[str, str] | None:
    token = (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()
    chat_id = (os.environ.get('TELEGRAM_CHAT_ID') or '').strip()
    if token and chat_id:
        return token, chat_id
    return None


def is_configured() -> bool:
    return _get_config() is not None


def _warn_missing_config() -> None:
    global _config_warned  # noqa: PLW0603
    if _config_warned:
        return
    _logger.warning(
        'order_bridge: Telegram omitido; faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID',
    )
    _config_warned = True


def send_message(text: str, *, order_ref: str | None = None) -> bool:
    """Envía ``text`` al chat configurado. Devuelve True si Telegram responde ok."""
    config = _get_config()
    if not config:
        return _warn_missing_config()
    token, chat_id = config
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': _PARSE_MODE,
    }
    url = _API_URL.format(token=token)
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        _logger.warning('order_bridge: error enviando Telegram: %s', e)
        return False
    if not body.get('ok'):
        _logger.warning(
            'order_bridge: Telegram rechazó el mensaje: %s',
            body.get('description', body),
        )
        return False
    _logger.info(
        'order_bridge: notificación Telegram enviada pedido ref=%s',
        order_ref or '-',
    )
    return True
