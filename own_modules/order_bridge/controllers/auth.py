# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from ..schemas import (
    ProfilePatchBody,
    ProfilePutBody,
    RegisterBody,
)
from ..schemas.responses import MessageErrorResponse, RegisterOkResponse, StatusResponse
from ..utils.decorators import (
    api_cors_preflight,
    api_device_auth,
    api_json_response,
    api_validated_json_body,
)
from ..utils.serialization import order_bridge_profile_to_response


class DeviceAuthController(http.Controller):
    @http.route('/api/order_bridge/register', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    @api_validated_json_body(RegisterBody)
    def register(self, body=None, **kwargs):
        try:
            result = request.env['order_bridge.device'].register_or_get(
                body.phone,
                body.device_key,
                body.device_info,
            )
        except UserError as e:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(e)),
                400,
            )
        device = result['device']
        partner = result['partner']
        return api_json_response(RegisterOkResponse(
            status='ok',
            created=result['created'],
            partner_id=partner.id,
            validated=device.phone_validated,
        ))

    @http.route('/api/order_bridge/status', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def status(self, api_device=None, api_partner=None, **kwargs):
        return api_json_response(StatusResponse(
            validated=api_device.phone_validated,
            phone=api_device.phone,
            partner_name=api_partner.name,
            partner_id=api_partner.id,
        ))

    @http.route('/api/order_bridge/profile', type='http', auth='public', methods=['GET'], csrf=False)
    @api_device_auth
    def profile_get(self, api_device=None, api_partner=None, **kwargs):
        p = api_partner.sudo()
        return api_json_response(self._profile_payload(api_device, p))

    @http.route('/api/order_bridge/profile', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def profile_options(self, **kwargs):
        return api_cors_preflight()

    @http.route('/api/order_bridge/profile', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_device_auth
    @api_validated_json_body(ProfilePutBody)
    def profile_put(self, api_device=None, api_partner=None, body=None, **kwargs):
        p = api_partner.sudo()
        PartnerAddress = request.env['order_bridge.partner_address']
        try:
            PartnerAddress.order_bridge_put_full(
                p,
                body.name,
                street=body.address.street,
                neighborhood=body.address.neighborhood,
                municipality=body.address.municipality,
                state=body.address.state,
            )
        except UserError as e:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(e)),
                400,
            )
        p.invalidate_recordset()
        return api_json_response(self._profile_payload(api_device, p))

    @http.route('/api/order_bridge/profile', type='http', auth='public', methods=['PATCH'], csrf=False)
    @api_device_auth
    @api_validated_json_body(ProfilePatchBody)
    def profile_patch(self, api_device=None, api_partner=None, body=None, **kwargs):
        p = api_partner.sudo()
        PartnerAddress = request.env['order_bridge.partner_address']
        addr_patch = None
        if body.address is not None:
            addr_patch = body.address.model_dump(exclude_unset=True)
        try:
            PartnerAddress.order_bridge_patch(
                p,
                name=body.name,
                address=addr_patch,
            )
        except UserError as e:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(e)),
                400,
            )
        p.invalidate_recordset()
        return api_json_response(self._profile_payload(api_device, p))

    def _profile_payload(self, api_device, partner_sudo):
        return order_bridge_profile_to_response(partner_sudo, api_device)
