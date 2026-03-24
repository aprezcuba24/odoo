# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from .decorators import (
    get_json_body,
    mobile_auth,
    mobile_cors_preflight,
    mobile_json_response,
)


class MobileAuthController(http.Controller):
    @http.route('/api/mobile/register', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def mobile_register(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return mobile_cors_preflight()
        body = get_json_body()
        if body is None:
            return mobile_json_response({'error': 'invalid_json'}, 400)
        phone = body.get('phone')
        device_key = body.get('device_key')
        name = body.get('name') or ''
        device_info = body.get('device_info')
        try:
            result = request.env['mobile.device'].register_or_get(phone, device_key, name, device_info)
        except UserError as e:
            return mobile_json_response({'error': 'validation', 'message': str(e)}, 400)
        device = result['device']
        partner = result['partner']
        return mobile_json_response({
            'status': 'ok',
            'created': result['created'],
            'partner_id': partner.id,
            'validated': device.phone_validated,
        })

    @http.route('/api/mobile/status', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth
    def mobile_status(self, mobile_device=None, mobile_partner=None, **kwargs):
        return mobile_json_response({
            'validated': mobile_device.phone_validated,
            'phone': mobile_device.phone,
            'partner_name': mobile_partner.name,
            'partner_id': mobile_partner.id,
        })

    @http.route('/api/mobile/profile', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth
    def mobile_profile(self, mobile_device=None, mobile_partner=None, **kwargs):
        p = mobile_partner.sudo()
        return mobile_json_response({
            'id': p.id,
            'name': p.name,
            'phone': p.phone or mobile_device.phone,
            'email': p.email,
        })
