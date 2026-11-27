# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import Command, http
from odoo.exceptions import LockError, UserError
from odoo.http import request
from odoo.tools.float_utils import float_compare

from odoo.addons.order_bridge.utils.constant import (
    DELIVERY_NOTE_MAX_LENGTH,
    STATE_DELIVERED,
    STATE_READY_FOR_DELIVERY,
)
from odoo.addons.order_bridge.utils.decorators import CORS_HEADERS, api_cors_preflight
from odoo.addons.order_bridge.utils.mobile_auth import (
    MODULE_DELIVERY,
    messenger_has_module,
    resolve_messenger,
)
from odoo.addons.order_bridge.utils.mobile_deliveries import (
    delivery_note_to_remote,
    order_to_remote_delivery,
    parse_device_timestamp,
    utc_now_iso_ms,
)

_logger = logging.getLogger(__name__)


def _json(payload, status=200):
    return request.make_json_response(
        payload,
        status=status,
        headers=[('Content-Type', 'application/json; charset=utf-8'), *CORS_HEADERS],
    )


def _resolve_delivery_messenger():
    messenger = resolve_messenger()
    if not messenger or not messenger_has_module(messenger, MODULE_DELIVERY):
        return None
    return messenger


def _parse_order_identifier(identifier: str):
    """Return int order id from path identifier, or None if not a valid key."""
    if identifier is None:
        return None
    raw = str(identifier).strip()
    if not raw or not raw.isdigit():
        return None
    return int(raw)


def _parse_delivery_payment(raw_payment):
    """Validate optional ``payment`` object on POST .../delivered.

    Return ``(parsed_dict, None)`` or ``(None, 'invalid_payment')``.
    """
    if not isinstance(raw_payment, dict):
        return None, 'invalid_payment'

    for key in ('transferCodes', 'cash', 'paymentPending'):
        if key not in raw_payment:
            return None, 'invalid_payment'

    raw_codes = raw_payment['transferCodes']
    cash = raw_payment['cash']
    payment_pending = raw_payment['paymentPending']

    if not isinstance(raw_codes, list):
        return None, 'invalid_payment'
    if not isinstance(cash, bool) or not isinstance(payment_pending, bool):
        return None, 'invalid_payment'

    codes = []
    for item in raw_codes:
        if not isinstance(item, str) or not item.strip():
            return None, 'invalid_payment'
        codes.append(item.strip())

    if not codes and not cash and not payment_pending:
        return None, 'invalid_payment'

    return {
        'transfer_codes': codes,
        'cash': cash,
        'payment_pending': payment_pending,
    }, None


def _settlement_payment_vals(order, payment):
    """Payment line that clears the remaining balance when the order is not pending.

    Cash goes to the Efectivo method; otherwise the remainder is booked as Transferencia
    (no transfer_id, since the SMS amounts were already linked by POST /payments).
    Return None when nothing remains. Amounts are never taken from the request.
    """
    rounding = order.currency_id.rounding or 0.01
    already_paid = sum(order.order_bridge_payment_ids.mapped('amount'))
    remaining = order.amount_total - already_paid
    if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
        return None
    method_xmlid = (
        'order_bridge.payment_method_cash' if payment['cash']
        else 'order_bridge.payment_method_transfer'
    )
    return {
        'method_id': request.env.ref(method_xmlid).id,
        'amount': remaining,
    }


class MobileDeliveriesController(http.Controller):
    @http.route(
        '/api/mobile/v1/deliveries',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    def list_deliveries(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        messenger = _resolve_delivery_messenger()
        if not messenger:
            return _json({'error': 'unauthorized'}, 401)
        orders = request.env['sale.order'].sudo().search(
            [
                ('order_bridge_messenger_id', '=', messenger.id),
                ('order_bridge_store_state', '=', STATE_READY_FOR_DELIVERY),
                ('order_bridge_origin', 'in', ('app', 'admin')),
            ],
            order='id asc',
        )
        return _json([order_to_remote_delivery(order) for order in orders], 200)

    @http.route(
        '/api/mobile/v1/deliveries/<path:identifier>/delivered',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def mark_delivered(self, identifier, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        messenger = _resolve_delivery_messenger()
        if not messenger:
            return _json({'error': 'unauthorized'}, 401)

        body = request.httprequest.get_data(cache=True, as_text=True) or ''
        try:
            payload = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            return _json({'error': 'invalid_json'}, 400)
        if not isinstance(payload, dict):
            return _json({'error': 'invalid_body'}, 400)

        device_ts = parse_device_timestamp(payload.get('deviceTimestamp'))
        if not device_ts:
            return _json({'error': 'invalid_device_timestamp'}, 400)

        order_id = _parse_order_identifier(identifier)
        if order_id is None:
            return _json({'error': 'not_found'}, 404)

        Order = request.env['sale.order'].sudo()
        order = Order.browse(order_id).exists()
        if not order:
            return _json({'error': 'not_found'}, 404)
        if order.order_bridge_messenger_id.id != messenger.id:
            return _json({'error': 'not_found'}, 404)
        if order.order_bridge_origin not in ('app', 'admin'):
            return _json({'error': 'not_found'}, 404)

        try:
            order.lock_for_update()
        except LockError:
            return _json({'error': 'locked'}, 429)

        order.invalidate_recordset()
        if order.order_bridge_delivery_received_at:
            return _json(
                {'serverReceivedAt': order.order_bridge_delivery_received_at},
                200,
            )

        if order.order_bridge_store_state == STATE_DELIVERED:
            # Delivered in backend without API stamp: create stable stamp now.
            stamp = utc_now_iso_ms()
            order.write({
                'order_bridge_delivery_received_at': stamp,
                'order_bridge_delivery_device_at': device_ts,
            })
            return _json({'serverReceivedAt': stamp}, 200)

        if order.order_bridge_store_state != STATE_READY_FOR_DELIVERY:
            return _json({'error': 'conflict'}, 409)

        payment = None
        if 'payment' in payload:
            payment, payment_error = _parse_delivery_payment(payload['payment'])
            if payment_error:
                return _json({'error': payment_error}, 400)

            Transfer = request.env['order_bridge.transfer'].sudo().with_context(active_test=False)
            for code in payment['transfer_codes']:
                transfer = Transfer.search(
                    [('transfer_type', '=', 'mobile'), ('code', '=', code)],
                    limit=1,
                )
                if not transfer or transfer.order_id.id != order.id:
                    return _json({'error': 'transfer_not_linked'}, 409)

        stamp = utc_now_iso_ms()
        write_vals = {
            'order_bridge_store_state': STATE_DELIVERED,
            'order_bridge_delivery_received_at': stamp,
            'order_bridge_delivery_device_at': device_ts,
        }
        if payment is not None:
            write_vals['order_bridge_payment_pending'] = payment['payment_pending']
            if not payment['payment_pending']:
                settlement = _settlement_payment_vals(order, payment)
                if settlement:
                    write_vals['order_bridge_payment_ids'] = [Command.create(settlement)]

        try:
            order.write(write_vals)
        except UserError:
            _logger.info(
                'mobile delivery rejected order_id=%s messenger_id=%s',
                order.id,
                messenger.id,
                exc_info=True,
            )
            return _json({'error': 'conflict'}, 409)

        return _json({'serverReceivedAt': stamp}, 200)

    @http.route(
        '/api/mobile/v1/deliveries/<path:identifier>/notes',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def create_delivery_note(self, identifier, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        messenger = _resolve_delivery_messenger()
        if not messenger:
            return _json({'error': 'unauthorized'}, 401)

        body = request.httprequest.get_data(cache=True, as_text=True) or ''
        try:
            payload = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            return _json({'error': 'invalid_json'}, 400)
        if not isinstance(payload, dict):
            return _json({'error': 'invalid_body'}, 400)

        note_raw = payload.get('note')
        if not isinstance(note_raw, str):
            return _json({'error': 'invalid_note'}, 400)
        note_text = note_raw.strip()
        if not note_text or len(note_text) > DELIVERY_NOTE_MAX_LENGTH:
            return _json({'error': 'invalid_note'}, 400)

        order_id = _parse_order_identifier(identifier)
        if order_id is None:
            return _json({'error': 'not_found'}, 404)

        Order = request.env['sale.order'].sudo()
        order = Order.browse(order_id).exists()
        if not order:
            return _json({'error': 'not_found'}, 404)
        if order.order_bridge_messenger_id.id != messenger.id:
            return _json({'error': 'not_found'}, 404)
        if order.order_bridge_origin not in ('app', 'admin'):
            return _json({'error': 'not_found'}, 404)

        try:
            order.lock_for_update()
        except LockError:
            return _json({'error': 'locked'}, 429)

        order.invalidate_recordset()
        if order.order_bridge_store_state not in (STATE_READY_FOR_DELIVERY, STATE_DELIVERED):
            return _json({'error': 'conflict'}, 409)

        note = request.env['order_bridge.delivery.note'].sudo().create({
            'order_id': order.id,
            'author': 'messenger',
            'body': note_text,
            'messenger_id': messenger.id,
        })
        return _json(delivery_note_to_remote(note), 201)
