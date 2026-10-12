# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from odoo.addons.order_bridge.utils.order_stock import (
    filter_available_products,
    get_catalog_warehouse,
)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    order_bridge_store_link = fields.Char(
        string='Enlace Tienda Apk',
        compute='_compute_order_bridge_store_link',
    )

    def _compute_order_bridge_store_link(self):
        for product in self:
            product.order_bridge_store_link = f'/product/{product.id}' if product.id else False

    @api.model
    def get_whatsapp_publisher_products(self):
        """Sellable storable variants with free stock for the WhatsApp publisher UI.

        Returns every matching product (visible in Tienda Apk or not). The client
        filters visibility in the browser. Each row includes ``order_bridge_visible``.
        """
        company = self.env.company
        domain = [
            ('sale_ok', '=', True),
            ('active', '=', True),
            ('is_storable', '=', True),
            '|',
            ('product_tmpl_id.company_id', '=', False),
            ('product_tmpl_id.company_id', '=', company.id),
        ]
        products = self.search(domain, order='name, id')
        stock_installed, warehouse, precision = get_catalog_warehouse(self.env, company)
        available = filter_available_products(
            products, stock_installed, warehouse, precision,
        )
        if warehouse:
            available = available.with_context(warehouse_id=warehouse.id)

        rows = []
        for product in available:
            tmpl = product.product_tmpl_id
            image_url = False
            if product.image_variant_1920 or tmpl.image_1920:
                image_url = f'/web/image/product.product/{product.id}/image_128'
            rows.append({
                'id': product.id,
                'name': product.display_name,
                'uom_name': product.uom_id.name if product.uom_id else False,
                'default_code': product.default_code or False,
                'barcode': product.barcode or False,
                'list_price': float(product.lst_price),
                'currency_id': product.currency_id.id,
                'free_qty': float(product.free_qty),
                'image_url': image_url,
                'order_bridge_visible': bool(tmpl.order_bridge_visible),
            })
        return rows

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
