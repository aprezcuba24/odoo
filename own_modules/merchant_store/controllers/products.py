# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.order_bridge.schemas.responses import SimpleErrorResponse
from odoo.addons.order_bridge.utils.decorators import (
    api_device_auth,
    api_json_response,
    api_validated_query,
)

from ..schemas import ProductsListQuery
from ..utils.catalog import merchant_store_product_domain
from ..utils.decorators import api_merchant_store_enabled
from ..utils.serialization import product_to_detail_response, products_page_response


class MerchantStoreProductsController(http.Controller):
    @http.route(
        '/api/merchant_store/products',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    @api_validated_query(ProductsListQuery)
    def products(self, api_device=None, q=None, **kwargs):
        company = api_device.sudo().company_id
        domain = list(merchant_store_product_domain(company))
        if q.merchant_id is not None:
            domain.append(('product_tmpl_id.merchant_id', '=', q.merchant_id))
        if q.search:
            domain.append(('name', 'ilike', q.search))
        Product = request.env['product.product'].sudo().with_company(company)
        total = Product.search_count(domain)
        products = Product.search(
            domain, limit=q.limit, offset=q.offset, order='name, id',
        )
        return api_json_response(
            products_page_response(products, q.limit, q.offset, total),
        )

    @http.route(
        '/api/merchant_store/products/<int:product_id>',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    def product_detail(self, product_id, api_device=None, **kwargs):
        company = api_device.sudo().company_id
        domain = merchant_store_product_domain(company)
        product = request.env['product.product'].sudo().browse(product_id).exists()
        if not product or not product.filtered_domain(domain):
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return api_json_response(product_to_detail_response(product))
