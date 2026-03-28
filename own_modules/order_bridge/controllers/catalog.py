# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pydantic import ValidationError

from odoo import http
from odoo.http import request

from ..schemas import ProductsListQuery, pydantic_errors_to_api_body
from ..utils.decorators import api_device_auth, api_json_response
from ..utils.serialization import (
    pos_category_to_api_dict,
    product_product_to_api_dict,
    serialize_many,
    serialize_one,
    serialize_pagination,
)


class CatalogController(http.Controller):
    @http.route('/api/order_bridge/categories', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth(require_pos_config=True)
    def categories(self, pos_config=None, **kwargs):
        PosCategory = request.env['pos.category'].sudo()
        domain = PosCategory._load_pos_data_domain({}, pos_config)
        categories = PosCategory.search(domain, order='sequence, id, name')
        items = serialize_many(categories, pos_category_to_api_dict)
        return api_json_response({'items': items, 'total': len(items)})

    @http.route('/api/order_bridge/products', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth(require_pos_config=True)
    def products(self, pos_config=None, product_domain=None, **kwargs):
        try:
            q = ProductsListQuery.from_request_params(request.params)
        except ValidationError as e:
            return api_json_response(pydantic_errors_to_api_body(e), 400)
        domain = list(product_domain)
        if q.category_id is not None:
            domain.append(('product_tmpl_id.categ_id', 'child_of', q.category_id))
        if q.pos_category_id is not None:
            domain.append(('product_tmpl_id.pos_categ_ids', 'child_of', q.pos_category_id))
        Product = request.env['product.product'].sudo()
        products = Product.search(domain, limit=q.limit, offset=q.offset, order='name, id')
        total = Product.search_count(domain)
        data = serialize_many(products, product_product_to_api_dict)
        return api_json_response(serialize_pagination(data, q.limit, q.offset, total, pos_config.id))

    @http.route('/api/order_bridge/products/<int:product_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth(require_pos_config=True)
    def product_detail(self, product_id, pos_config=None, product_domain=None, **kwargs):
        prod = request.env['product.product'].sudo().browse(product_id).exists()
        if not prod:
            return api_json_response({'error': 'not_found'}, 404)
        if not prod.filtered_domain(product_domain):
            return api_json_response({'error': 'not_found'}, 404)
        payload = serialize_one(
            prod,
            product_product_to_api_dict,
            include_description_sale=True,
        )
        payload['pos_config_id'] = pos_config.id
        return api_json_response(payload)
