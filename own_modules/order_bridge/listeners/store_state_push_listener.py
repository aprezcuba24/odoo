# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api
from odoo.modules.registry import Registry

from odoo.addons.order_bridge.utils.push_order_message import format_store_state_push

_logger = logging.getLogger(__name__)


def order_bridge_store_state_push(order, old_entity, new_entity):
    if order.order_bridge_origin not in ('app', 'admin'):
        return
    old_ss = old_entity.get('order_bridge_store_state') if old_entity else None
    new_ss = new_entity.order_bridge_store_state
    if old_ss == new_ss:
        return
    if not order.partner_id:
        return
    _schedule_store_state_push(order)


def _schedule_store_state_push(order):
    """Send FCM after commit so rolled-back writes do not notify."""
    order.ensure_one()
    order_id = order.id
    dbname = order.env.cr.dbname

    @order.env.cr.postcommit.add
    def _send_store_state_push():
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            loaded = env['sale.order'].browse(order_id).exists()
            if not loaded or not loaded.partner_id:
                return
            title, body, data = format_store_state_push(loaded)
            try:
                env['order_bridge.fcm'].send_to_partner(
                    loaded.partner_id.id,
                    title,
                    body,
                    data=data,
                )
            except Exception:
                _logger.exception(
                    'order_bridge: push store_state falló order_id=%s partner_id=%s',
                    order_id,
                    loaded.partner_id.id,
                )
