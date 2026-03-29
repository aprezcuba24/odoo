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
    def categories(self, pos_config=None, **kwargs):
        PosCategory = request.env['pos.category'].sudo()
        domain = PosCategory._load_pos_data_domain({}, pos_config)
        categories = PosCategory.search(domain, order='sequence, id, name')
        return api_json_response(categories_list_response(categories))

    @http.route('/api/order_bridge/products', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_access
    @api_validated_query(ProductsListQuery)
    def products(self, pos_config=None, product_domain=None, q=None, **kwargs):
        domain = list(product_domain)
        if q.category_id is not None:
            domain.append(('product_tmpl_id.categ_id', 'child_of', q.category_id))
        if q.pos_category_id is not None:
            domain.append(('product_tmpl_id.pos_categ_ids', 'child_of', q.pos_category_id))
        Product = request.env['product.product'].sudo()
        products = Product.search(domain, limit=q.limit, offset=q.offset, order='name, id')
        total = Product.search_count(domain)
        return api_json_response(
            products_page_response(products, q.limit, q.offset, total, pos_config.id),
        )

    @http.route('/api/order_bridge/products/<int:product_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_access
    def product_detail(self, product_id, pos_config=None, product_domain=None, **kwargs):
        prod = request.env['product.product'].sudo().browse(product_id).exists()
        if not prod:
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        if not prod.filtered_domain(product_domain):
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return api_json_response(product_to_detail_response(prod, pos_config.id))
