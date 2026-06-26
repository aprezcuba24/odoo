# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.addons.order_bridge.utils.order_stock import (
    filter_available_products,
    get_catalog_warehouse,
)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _mcp_api_category_response(self, categ):
        if not categ:
            return False
        return {
            'id': categ.id,
            'name': categ.name,
            'parent_id': categ.parent_id.id if categ.parent_id else False,
        }

    @api.model
    def _mcp_api_product_response(self, product):
        tmpl = product.product_tmpl_id
        return {
            'id': product.id,
            'name': product.display_name,
            'default_code': product.default_code or False,
            'list_price': float(product.lst_price),
            'uom_name': product.uom_id.name if product.uom_id else False,
            'barcode': product.barcode or False,
            'category': self._mcp_api_category_response(tmpl.categ_id),
        }

    @api.model
    def _mcp_api_products_page_response(self, products, limit, offset, total):
        return {
            'items': [self._mcp_api_product_response(product) for product in products],
            'limit': limit,
            'offset': offset,
            'total': total,
        }

    @api.model
    def _mcp_api_product_search_domain(self, query=None, category_id=None):
        """Domain: Tienda Apk catalog; optional category and text filters."""
        company = self.env.company
        domain = list(company._order_bridge_product_domain())
        if category_id is not None:
            categ_id = int(category_id)
            if categ_id <= 0:
                raise ValidationError(_('category_id debe ser un entero positivo.'))
            if not self.env['product.category'].browse(categ_id).exists():
                raise ValidationError(_('Categoría %(cid)s no encontrada.', cid=categ_id))
            domain.append(('product_tmpl_id.categ_id', 'child_of', categ_id))
        if query is not None and str(query).strip():
            term = str(query).strip()
            domain.extend([
                '|',
                ('name', 'ilike', term),
                ('product_tmpl_id.categ_id.complete_name', 'ilike', term),
            ])
        return domain

    @api.model
    def api_get_product(self, product_id):
        """Return one Tienda Apk product by id (JSON-2 / MCP).

        Same availability rules as ``api_search_products``. Runs as
        ``self.env.user``; ACL and record rules apply.

        :param int product_id: ``product.product`` id.
        :returns: dict with id, name, price, uom, barcode and category
        """
        company = self.env.company
        Product = self.with_company(company)
        products = Product.search(
            company._order_bridge_product_domain() + [('id', '=', int(product_id))],
        )
        stock_installed, warehouse, precision = get_catalog_warehouse(self.env, company)
        product = filter_available_products(products, stock_installed, warehouse, precision)
        if not product:
            raise ValidationError(
                _('El producto %(pid)s no está disponible.', pid=product_id),
            )
        return self._mcp_api_product_response(product)

    @api.model
    def api_search_products(self, query=None, limit=80, offset=0, category_id=None):
        """Search products available for Tienda Apk by name or category (JSON-2 / MCP).

        Returns only products in the Tienda Apk catalog (``order_bridge_visible``,
        ``sale_ok``, ``active``, company) with available stock (same rules as
        ``GET /api/order_bridge/products``). When ``query`` is omitted or blank,
        no text filter is applied. ``category_id`` restricts to that category
        and its descendants (``child_of``). Pagination uses ``limit`` and
        ``offset`` after the stock filter. Runs as ``self.env.user``; ACL and
        record rules apply.

        :param str query: Optional free-text search term (name or category name).
        :param int limit: Page size (default 80, max 200).
        :param int offset: Rows to skip after stock filter (default 0).
        :param int category_id: Optional ``product.category`` id (``child_of``).
        :returns: dict with items, limit, offset and total
        """
        limit = min(max(int(limit or 80), 1), 200)
        offset = max(int(offset or 0), 0)
        company = self.env.company
        Product = self.with_company(company)
        products = Product.search(
            self._mcp_api_product_search_domain(query, category_id=category_id),
            order='name, id',
        )
        stock_installed, warehouse, precision = get_catalog_warehouse(self.env, company)
        available = filter_available_products(products, stock_installed, warehouse, precision)
        total = len(available)
        page = available[offset:offset + limit]
        return self._mcp_api_products_page_response(page, limit, offset, total)
