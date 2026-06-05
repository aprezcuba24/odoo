# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.order_bridge.utils.telegram_client import send_message
from odoo.addons.order_bridge.utils.telegram_order_message import format_order_created_message


def order_bridge_order_created(order, old_entity, new_entity):
    if order.order_bridge_origin != 'app':
        return
    text = format_order_created_message(order)
    send_message(text, order_ref=order.order_bridge_ref)
