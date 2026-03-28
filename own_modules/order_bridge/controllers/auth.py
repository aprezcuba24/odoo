# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from ..models.partner_address import ADDRESS_FIELD_NAMES
from ..utils.decorators import (
    api_cors_preflight,
    api_device_auth,
    api_json_response,
    get_json_body,
)
from ..utils.serialization import order_bridge_profile_to_api_dict


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
        device_info = body.get('device_info')
        try:
            result = request.env['order_bridge.device'].register_or_get(phone, device_key, device_info)
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

    @http.route(
        '/api/order_bridge/profile',
        type='http',
        auth='public',
        methods=['GET', 'PUT', 'PATCH', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    def profile(self, api_device=None, api_partner=None, **kwargs):
        method = request.httprequest.method
        if method == 'GET':
            return self._profile_get(api_device, api_partner)
        if method == 'OPTIONS':
            return self._profile_options()
        body = get_json_body()
        if body is None:
            return api_json_response({'error': 'invalid_json'}, 400)
        if method == 'PUT':
            return self._profile_put(api_device, api_partner, body)
        if method == 'PATCH':
            return self._profile_patch(api_device, api_partner, body)
        return self._profile_options()

    def _profile_get(self, api_device, api_partner):
        p = api_partner.sudo()
        return api_json_response(self._profile_payload(api_device, p))

    def _profile_options(self):
        return api_cors_preflight()

    def _profile_payload(self, api_device, partner_sudo):
        return order_bridge_profile_to_api_dict(partner_sudo, api_device)

    def _profile_put(self, api_device, api_partner, body):
        p = api_partner.sudo()
        PartnerAddress = request.env['order_bridge.partner_address']
        name = body.get('name')
        if name is None or not str(name).strip():
            return api_json_response(
                {'error': 'validation', 'message': 'name is required'},
                400,
            )
        addr_obj = body.get('address')
        if not isinstance(addr_obj, dict):
            return api_json_response(
                {'error': 'validation', 'message': 'address object required'},
                400,
            )
        parts = {}
        for key in ADDRESS_FIELD_NAMES:
            if key not in addr_obj:
                return api_json_response(
                    {'error': 'validation', 'message': f'address.{key} is required'},
                    400,
                )
            raw = addr_obj[key]
            val = '' if raw is None else str(raw).strip()
            if not val:
                return api_json_response(
                    {'error': 'validation', 'message': f'address.{key} must be non-empty'},
                    400,
                )
            parts[key] = val
        try:
            PartnerAddress.order_bridge_put_full(p, str(name).strip(), **parts)
        except UserError as e:
            return api_json_response({'error': 'validation', 'message': str(e)}, 400)
        p.invalidate_recordset()
        return api_json_response(self._profile_payload(api_device, p))

    def _profile_patch(self, api_device, api_partner, body):
        p = api_partner.sudo()
        PartnerAddress = request.env['order_bridge.partner_address']
        name = body.get('name')
        addr_in = body.get('address')
        if name is not None and not str(name).strip():
            return api_json_response(
                {'error': 'validation', 'message': 'name cannot be empty'},
                400,
            )
        addr_patch = None
        if addr_in is not None:
            if not isinstance(addr_in, dict):
                return api_json_response(
                    {'error': 'validation', 'message': 'address must be an object'},
                    400,
                )
            addr_patch = {
                k: addr_in[k]
                for k in ADDRESS_FIELD_NAMES
                if k in addr_in
            }
        try:
            PartnerAddress.order_bridge_patch(
                p,
                name=str(name).strip() if name is not None else None,
                address=addr_patch,
            )
        except UserError as e:
            return api_json_response({'error': 'validation', 'message': str(e)}, 400)
        p.invalidate_recordset()
        return api_json_response(self._profile_payload(api_device, p))
