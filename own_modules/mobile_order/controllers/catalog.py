# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from .decorators import mobile_auth, mobile_json_response


class MobileCatalogController(http.Controller):
    @http.route('/api/mobile/products', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth
    def mobile_products(self, mobile_device=None, mobile_partner=None, **kwargs):
        limit = min(int(request.params.get('limit') or 80), 200)
        offset = int(request.params.get('offset') or 0)
        category_id = request.params.get('category_id')
        domain = [('sale_ok', '=', True), ('active', '=', True)]
        if category_id:
            try:
                cid = int(category_id)
                domain.append(('categ_id', 'child_of', cid))
            except ValueError:
                pass
        Product = request.env['product.product'].sudo()
        products = Product.search(domain, limit=limit, offset=offset, order='name, id')
        total = Product.search_count(domain)
        data = []
        for prod in products:
            data.append({
                'id': prod.id,
                'name': prod.display_name,
                'default_code': prod.default_code,
                'list_price': prod.lst_price,
                'uom_name': prod.uom_id.name if prod.uom_id else None,
                'barcode': prod.barcode,
            })
        return mobile_json_response({'items': data, 'total': total, 'limit': limit, 'offset': offset})

    @http.route('/api/mobile/products/<int:product_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth
    def mobile_product_detail(self, product_id, mobile_device=None, mobile_partner=None, **kwargs):
        prod = request.env['product.product'].sudo().browse(product_id).exists()
        if not prod or not prod.sale_ok or not prod.active:
            return mobile_json_response({'error': 'not_found'}, 404)
        return mobile_json_response({
            'id': prod.id,
            'name': prod.display_name,
            'default_code': prod.default_code,
            'list_price': prod.lst_price,
            'uom_name': prod.uom_id.name if prod.uom_id else None,
            'barcode': prod.barcode,
            'description_sale': prod.description_sale,
        })
