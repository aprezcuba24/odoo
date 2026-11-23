# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.order_bridge.utils.decorators import api_device_auth, api_json_response

from ..utils.decorators import api_merchant_store_enabled
from ..utils.serialization import merchants_list_response


class MerchantStoreMerchantsController(http.Controller):
    @http.route(
        '/api/merchant_store/merchants',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    def merchants(self, api_device=None, **kwargs):
        company = api_device.sudo().company_id
        merchants = request.env['merchant_store.merchant'].sudo().search([
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], order='name, id')
        return api_json_response(merchants_list_response(merchants))
