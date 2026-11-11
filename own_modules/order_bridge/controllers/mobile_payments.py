# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import http
from odoo.http import request

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

    return {
        'phone': phone.strip(),
        'amount': float(amount),
        'code': code.strip(),
    }, None


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

        result, backend_response = request.env['order_bridge.transfer'].sudo().process_mobile_payment(
            messenger,
            parsed['phone'],
            parsed['amount'],
            parsed['code'],
        )
        return _json({
            'result': result,
            'backendResponse': backend_response or '',
        }, 200)
