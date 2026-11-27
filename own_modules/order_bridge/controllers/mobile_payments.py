# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import http
from odoo.exceptions import LockError
from odoo.http import request

from odoo.addons.order_bridge.models.transfer import TransferLinkedToOtherOrderError
from odoo.addons.order_bridge.utils.decorators import CORS_HEADERS, api_cors_preflight
from odoo.addons.order_bridge.utils.mobile_auth import (
    MODULE_PAYMENTS,
    messenger_has_module,
    resolve_messenger,
)


def _json(payload, status=200):
    return request.make_json_response(
        payload,
        status=status,
        headers=[('Content-Type', 'application/json; charset=utf-8'), *CORS_HEADERS],
    )


def _parse_payment_body(raw_body):
    """Validate POST /payments body. Return (payload_dict, None) or (None, error_code)."""
    try:
        payload = json.loads(raw_body) if raw_body.strip() else None
    except json.JSONDecodeError:
        return None, 'invalid_body'
    if not isinstance(payload, dict):
        return None, 'invalid_body'

    phone = payload.get('phone')
    if not isinstance(phone, str) or not phone.strip():
        return None, 'invalid_phone'

    amount = payload.get('amount')
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        return None, 'invalid_amount'

    code = payload.get('code')
    if not isinstance(code, str) or not code.strip():
        return None, 'invalid_code'

    order_identifier = None
    if 'orderIdentifier' in payload and payload['orderIdentifier'] is not None:
        raw_order_id = payload['orderIdentifier']
        if not isinstance(raw_order_id, str) or not raw_order_id.strip():
            return None, 'invalid_order_identifier'
        order_identifier = raw_order_id.strip()

    return {
        'phone': phone.strip(),
        'amount': float(amount),
        'code': code.strip(),
        'order_identifier': order_identifier,
    }, None


def _resolve_messenger_order(messenger, order_identifier):
    """Find a sale.order belonging to the authenticated messenger, or None."""
    if not order_identifier or not order_identifier.isdigit():
        return None
    order = request.env['sale.order'].sudo().browse(int(order_identifier)).exists()
    if not order:
        return None
    if order.order_bridge_messenger_id.id != messenger.id:
        return None
    if order.company_id.id != messenger.company_id.id:
        return None
    if order.order_bridge_origin not in ('app', 'admin'):
        return None
    return order


class MobilePaymentsController(http.Controller):
    @http.route(
        '/api/mobile/v1/payments',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def create_payment(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()

        messenger = resolve_messenger()
        if not messenger or not messenger_has_module(messenger, MODULE_PAYMENTS):
            return _json({'error': 'unauthorized'}, 401)

        body = request.httprequest.get_data(cache=True, as_text=True) or ''
        parsed, error = _parse_payment_body(body)
        if error:
            return _json({'error': error}, 400)

        order = None
        if parsed['order_identifier'] is not None:
            order = _resolve_messenger_order(messenger, parsed['order_identifier'])
            if not order:
                return _json({'error': 'order_not_found'}, 404)

        try:
            result, backend_response = request.env['order_bridge.transfer'].sudo().process_mobile_payment(
                messenger,
                parsed['phone'],
                parsed['amount'],
                parsed['code'],
                order=order,
            )
        except TransferLinkedToOtherOrderError:
            return _json({'error': 'transfer_linked_to_other_order'}, 409)
        except LockError:
            return _json({'error': 'locked'}, 429)

        return _json({
            'result': result,
            'backendResponse': backend_response or '',
        }, 200)
