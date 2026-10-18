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
        filters visibility in the browser. Each row includes ``order_bridge_visible``,
        ``category_id``, ``category_name`` and ``category_sequence`` so the caller
        can group products by category in the correct order.

        Products are sorted by:
          1. category ``order_bridge_sequence`` (ascending)
          2. category ``complete_name`` (alphabetical fallback)
          3. category ``id``
          4. product ``name``
          5. product ``id``
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
        products = self.search(domain)
        stock_installed, warehouse, precision = get_catalog_warehouse(self.env, company)
        available = filter_available_products(
            products, stock_installed, warehouse, precision,
        )
        if warehouse:
            available = available.with_context(warehouse_id=warehouse.id)

        def _sort_key(p):
            categ = p.product_tmpl_id.categ_id
            if categ:
                seq = categ.order_bridge_sequence if categ.order_bridge_sequence is not False else 10
                cname = categ.complete_name or ''
                cid = categ.id
            else:
                seq, cname, cid = 9999, '', 0
            return (seq, cname, cid, p.name or '', p.id)

        rows = []
        for product in sorted(available, key=_sort_key):
            tmpl = product.product_tmpl_id
            categ = tmpl.categ_id
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
                'category_id': categ.id if categ else False,
                'category_name': categ.name if categ else False,
                'category_sequence': categ.order_bridge_sequence if categ else 10,
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
