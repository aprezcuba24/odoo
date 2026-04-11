# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from ..utils.decorators import api_access, api_json_response
from ..utils.serialization import municipalities_list_response


class MunicipalitiesController(http.Controller):
    @http.route(
        '/api/order_bridge/municipalities',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_access
    def municipalities(self, **kwargs):
        Municipality = request.env['order_bridge.municipality'].sudo()
        municipalities = Municipality.search([('active', '=', True)], order='name, id')
        return api_json_response(municipalities_list_response(municipalities))
