# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _order_bridge_product_domain(self):
        """Exclude merchant products from the Tienda Apk catalog."""
        return super()._order_bridge_product_domain() + [
            ('product_tmpl_id.merchant_id', '=', False),
        ]
