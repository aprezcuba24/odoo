# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Normalize order_bridge_store_state (NULL, legacy keys, unknown → reviewing)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order SET order_bridge_store_state = 'reviewing'
        WHERE order_bridge_store_state = 'reviewed'
        """
    )
    cr.execute(
        """
        UPDATE sale_order SET order_bridge_store_state = 'negotiating'
        WHERE order_bridge_store_state = 'negotiated'
        """
    )
    cr.execute(
        """
        UPDATE sale_order SET order_bridge_store_state = 'reviewing'
        WHERE order_bridge_store_state IS NULL
           OR order_bridge_store_state NOT IN (
               'reviewing', 'negotiating', 'ready_for_delivery', 'delivered'
           )
        """
    )
