# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Autenticación por X-Api-Key para la API móvil (/api/mobile/v1)."""

from __future__ import annotations

import hmac

from odoo.http import request

MODULE_DELIVERY = 'delivery'
MODULE_PAYMENTS = 'payments'


def resolve_messenger():
    """Return the active messenger for ``X-Api-Key``, or ``None``."""
    key = (request.httprequest.headers.get('X-Api-Key') or '').strip()
    if not key:
        return None
    Messenger = request.env['order_bridge.messenger'].sudo()
    messenger = Messenger.search([('api_key', '=', key), ('active', '=', True)], limit=1)
    if not messenger:
        return None
    if not hmac.compare_digest(messenger.api_key, key):
        return None
    return messenger


def messenger_module_ids(messenger):
    """Return the list of module id dicts granted to ``messenger``."""
    modules = []
    if messenger.module_delivery:
        modules.append({'id': MODULE_DELIVERY})
    if messenger.module_payments:
        modules.append({'id': MODULE_PAYMENTS})
    return modules


def messenger_has_module(messenger, module_id: str) -> bool:
    if module_id == MODULE_DELIVERY:
        return bool(messenger.module_delivery)
    if module_id == MODULE_PAYMENTS:
        return bool(messenger.module_payments)
    return False
