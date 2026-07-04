# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Texto y payload FCM para notificaciones push de cambio de estado tienda."""

from __future__ import annotations

from odoo import _
from odoo.addons.order_bridge.utils.constant import STORE_STATE_VALID_CHOICES


def format_store_state_push(order) -> tuple[str, str, dict[str, str]]:
    """Devuelve (title, body, data) para FCM tras un cambio de order_bridge_store_state."""
    selection_dict = dict(STORE_STATE_VALID_CHOICES)
    store_state_label = selection_dict.get(
        order.order_bridge_store_state,
        order.order_bridge_store_state or '',
    )
    title = _('Tu pedido %s') % (order.name or '')
    body = _('Estado actualizado: %s') % store_state_label
    data = {
        'type': 'order_status',
        'order_id': str(order.id),
    }
    return title, body, data
