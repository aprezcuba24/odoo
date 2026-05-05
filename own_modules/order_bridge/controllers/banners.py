# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from ..utils.decorators import api_access, api_json_response
from ..utils.serialization import banners_list_response


class BannersController(http.Controller):
    @http.route(
        '/api/order_bridge/banners',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_access
    def banners(self, catalog_company=None, product_domain=None, **kwargs):
        domain = [
            ('active', '=', True),
            ('company_id', '=', catalog_company.id),
        ]
        Banner = request.env['order_bridge.banner'].sudo().with_company(catalog_company)
        records = Banner.search(domain, order='sequence, id')
        return api_json_response(banners_list_response(records))
