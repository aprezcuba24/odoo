# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hmac
import json
import logging

from odoo import http
from odoo.exceptions import LockError, UserError
from odoo.http import request

from odoo.addons.order_bridge.utils.constant import (
    DELIVERY_NOTE_MAX_LENGTH,
    STATE_DELIVERED,
    STATE_READY_FOR_DELIVERY,
)
from odoo.addons.order_bridge.utils.decorators import CORS_HEADERS, api_cors_preflight
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


def _resolve_messenger():
    key = (request.httprequest.headers.get('X-Api-Key') or '').strip()
    if not key:
        return None
    Messenger = request.env['order_bridge.messenger'].sudo()
    messenger = Messenger.search([('api_key', '=', key), ('active', '=', True)], limit=1)
    if not messenger:
        return None
    if not hmac.compare_digest(messenger.api_key, key):
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
        messenger = _resolve_messenger()
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
        messenger = _resolve_messenger()
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

        stamp = utc_now_iso_ms()
        try:
            order.write({
                'order_bridge_store_state': STATE_DELIVERED,
                'order_bridge_delivery_received_at': stamp,
                'order_bridge_delivery_device_at': device_ts,
            })
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
        messenger = _resolve_messenger()
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
