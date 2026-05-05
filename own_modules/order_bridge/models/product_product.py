# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _can_return_content(self, field_name=None, access_token=None):
        """Allow public ``/web/image`` for Tienda Apk catalog or lines of pedidos API."""
        if field_name not in ('image_128', 'image_256', 'image_512'):
            return super()._can_return_content(field_name, access_token)
        self.ensure_one()
        p = self.sudo()
        tmpl = p.product_tmpl_id
        if not (p.sale_ok and p.active):
            return False
        if tmpl.company_id and tmpl.company_id != self.env.company:
            return False
        if tmpl.order_bridge_visible:
            return True
        # Product ordered via Tienda Apk: show in order detail even if later removed from catalog
        return bool(
            self.env['sale.order.line'].sudo().search(
                [
                    ('product_id', '=', p.id),
                    ('order_id.order_bridge_origin', 'in', ('app', 'admin')),
                ],
                limit=1,
            )
        )
