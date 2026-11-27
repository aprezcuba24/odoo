# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Drop unused order_id column from order_bridge_transfer."""


def migrate(cr, version):
    cr.execute('ALTER TABLE order_bridge_transfer DROP COLUMN IF EXISTS order_id')
