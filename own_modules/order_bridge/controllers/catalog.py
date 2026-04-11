# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from ..schemas import ProductsListQuery
from ..schemas.responses import SimpleErrorResponse
from ..utils.decorators import api_access, api_json_response, api_validated_query
from ..utils.serialization import (
    categories_list_response,
    product_to_detail_response,
    products_page_response,
)


class CatalogController(http.Controller):
    @http.route('/api/order_bridge/categories', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_access
    def categories(self, product_domain=None, **kwargs):
        Product = request.env['product.product'].sudo()
        Category = request.env['product.category'].sudo()
        categ_ids = list({cid for cid in Product.search(product_domain).mapped('product_tmpl_id.categ_id').ids if cid})
        if not categ_ids:
            categories = Category.browse([])
        else:
            categories = Category.search([('id', 'in', categ_ids)], order='complete_name, id')
        return api_json_response(categories_list_response(categories))

    @http.route('/api/order_bridge/products', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_access
    @api_validated_query(ProductsListQuery)
    def products(self, product_domain=None, q=None, **kwargs):
        domain = list(product_domain)
        if q.category_id is not None:
            domain.append(('product_tmpl_id.categ_id', 'child_of', q.category_id))
        Product = request.env['product.product'].sudo()
        products = Product.search(domain, limit=q.limit, offset=q.offset, order='name, id')
        total = Product.search_count(domain)
        return api_json_response(
            products_page_response(products, q.limit, q.offset, total),
        )

    @http.route('/api/order_bridge/products/<int:product_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_access
    def product_detail(self, product_id, product_domain=None, **kwargs):
        prod = request.env['product.product'].sudo().browse(product_id).exists()
        if not prod:
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        if not prod.filtered_domain(product_domain):
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return api_json_response(product_to_detail_response(prod))
