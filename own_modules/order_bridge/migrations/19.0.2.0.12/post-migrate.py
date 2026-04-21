# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Map store state keys reviewed→reviewing, negotiated→negotiating."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order
        SET order_bridge_store_state = 'reviewing'
        WHERE order_bridge_store_state = 'reviewed'
        """
    )
    cr.execute(
        """
        UPDATE sale_order
        SET order_bridge_store_state = 'negotiating'
        WHERE order_bridge_store_state = 'negotiated'
        """
    )
