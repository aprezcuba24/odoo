# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from .decorators import mobile_auth, mobile_json_response
from .serialization import (
    pos_category_to_mobile_dict,
    product_product_to_mobile_dict,
    serialize_many,
    serialize_one,
)


class MobileCatalogController(http.Controller):
    @http.route('/api/mobile/categories', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth(require_pos_config=True)
    def mobile_categories(self, mobile_pos_config=None, **kwargs):
        PosCategory = request.env['pos.category'].sudo()
        domain = PosCategory._load_pos_data_domain({}, mobile_pos_config)
        categories = PosCategory.search(domain, order='sequence, id, name')
        items = serialize_many(categories, pos_category_to_mobile_dict)
        return mobile_json_response({'items': items, 'total': len(items)})

    @http.route('/api/mobile/products', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth(require_pos_config=True)
    def mobile_products(self, mobile_device=None, mobile_partner=None, mobile_pos_config=None, mobile_product_domain=None, **kwargs):
        limit = min(int(request.params.get('limit') or 80), 200)
        offset = int(request.params.get('offset') or 0)
        domain = list(mobile_product_domain)
        category_id = request.params.get('category_id')
        if category_id:
            try:
                cid = int(category_id)
                domain.append(('product_tmpl_id.categ_id', 'child_of', cid))
            except ValueError:
                pass
        pos_category_id = request.params.get('pos_category_id')
        if pos_category_id:
            try:
                pcid = int(pos_category_id)
                domain.append(('product_tmpl_id.pos_categ_ids', 'child_of', pcid))
            except ValueError:
                pass
        Product = request.env['product.product'].sudo()
        products = Product.search(domain, limit=limit, offset=offset, order='name, id')
        total = Product.search_count(domain)
        data = serialize_many(products, product_product_to_mobile_dict)
        return mobile_json_response({
            'items': data,
            'total': total,
            'limit': limit,
            'offset': offset,
            'pos_config_id': mobile_pos_config.id,
        })

    @http.route('/api/mobile/products/<int:product_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth(require_pos_config=True)
    def mobile_product_detail(self, product_id, mobile_device=None, mobile_partner=None, mobile_pos_config=None, mobile_product_domain=None, **kwargs):
        prod = request.env['product.product'].sudo().browse(product_id).exists()
        if not prod:
            return mobile_json_response({'error': 'not_found'}, 404)
        if not prod.filtered_domain(mobile_product_domain):
            return mobile_json_response({'error': 'not_found'}, 404)
        payload = serialize_one(
            prod,
            product_product_to_mobile_dict,
            include_description_sale=True,
        )
        payload['pos_config_id'] = mobile_pos_config.id
        return mobile_json_response(payload)
