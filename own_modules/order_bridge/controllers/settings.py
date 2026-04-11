# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from ..utils.decorators import api_access, api_json_response
from ..utils.serialization import general_settings_response


class SettingsController(http.Controller):
    @http.route(
        '/api/order_bridge/settings',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_access
    def settings(self, catalog_company=None, product_domain=None, **kwargs):
        company = catalog_company if catalog_company is not None else request.env.company.sudo()
        Settings = request.env['order_bridge.general_settings'].sudo()
        rec = Settings._get_or_create_for_company(company)
        return api_json_response(general_settings_response(rec))
