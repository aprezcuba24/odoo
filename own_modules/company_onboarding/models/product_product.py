# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _can_return_content(self, field_name=None, access_token=None):
        if field_name in ('image_128', 'image_256', 'image_512'):
            self.ensure_one()
            tmpl = self.sudo().product_tmpl_id
            if tmpl.company_id != self.env.company:
                return False
        return super()._can_return_content(field_name, access_token)
