# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Allow order_bridge_store_state = canceled in normalization list."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order SET order_bridge_store_state = 'reviewing'
        WHERE order_bridge_store_state IS NULL
           OR order_bridge_store_state NOT IN (
               'reviewing', 'negotiating', 'ready_for_delivery', 'delivered', 'canceled'
           )
        """
    )
