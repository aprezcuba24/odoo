# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from ..utils.decorators import (
    api_cors_preflight,
    api_device_auth,
    api_json_response,
    get_json_body,
)


class DeviceAuthController(http.Controller):
    @http.route('/api/order_bridge/register', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def register(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        body = get_json_body()
        if body is None:
            return api_json_response({'error': 'invalid_json'}, 400)
        phone = body.get('phone')
        device_key = body.get('device_key')
        name = body.get('name') or ''
        device_info = body.get('device_info')
        try:
            result = request.env['order_bridge.device'].register_or_get(phone, device_key, name, device_info)
        except UserError as e:
            return api_json_response({'error': 'validation', 'message': str(e)}, 400)
        device = result['device']
        partner = result['partner']
        return api_json_response({
            'status': 'ok',
            'created': result['created'],
            'partner_id': partner.id,
            'validated': device.phone_validated,
        })

    @http.route('/api/order_bridge/status', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def status(self, api_device=None, api_partner=None, **kwargs):
        return api_json_response({
            'validated': api_device.phone_validated,
            'phone': api_device.phone,
            'partner_name': api_partner.name,
            'partner_id': api_partner.id,
        })

    @http.route('/api/order_bridge/profile', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def profile(self, api_device=None, api_partner=None, **kwargs):
        p = api_partner.sudo()
        return api_json_response({
            'id': p.id,
            'name': p.name,
            'phone': p.phone or api_device.phone,
            'email': p.email,
        })
