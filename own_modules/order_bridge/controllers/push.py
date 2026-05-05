# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import http
from odoo.http import request

from ..schemas import PushTokenBody, PushTopicsOkResponse, PushTopicsPatchBody
from ..schemas.responses import ConfigurationErrorResponse, MessageErrorResponse
from ..utils import fcm_client
from ..utils.decorators import (
    api_device_auth,
    api_json_response,
    api_validated_json_body,
)

_logger = logging.getLogger(__name__)


def _subscribed_effective(
    fcm_str: str,
    subscribe_list: list[str],
) -> list[str]:
    """Aplica suscripciones; ante fallo de un topic se registra y se sigue. Lista = efectiva."""
    effective: list[str] = []
    for topic in subscribe_list:
        if fcm_client.subscribe_to_topic([fcm_str], topic):
            effective.append(topic)
    return effective


class PushController(http.Controller):
    @http.route(
        '/api/order_bridge/push/token',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_validated_json_body(PushTokenBody)
    def push_token(self, body=None, api_device=None, api_partner=None, **kwargs):
        Push = request.env['order_bridge.push_token']
        _ = api_partner
        Push.order_bridge_upsert_for_device(
            api_device,
            body.fcm_token,
            body.platform,
        )
        fcm = body.fcm_token
        try:
            fcm_client.ensure_firebase_app()
        except fcm_client.FcmConfigurationError as e:
            return api_json_response(
                ConfigurationErrorResponse(error='configuration', message=str(e)),
                503,
            )
        sub_ok = _subscribed_effective(fcm, list(body.subscribe_topics or []))
        return api_json_response(
            PushTopicsOkResponse(
                status='ok',
                subscribed_topics=sub_ok,
            ),
        )

    @http.route(
        '/api/order_bridge/push/topics',
        type='http',
        auth='public',
        methods=['PATCH', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_validated_json_body(PushTopicsPatchBody)
    def push_topics(self, body=None, api_device=None, api_partner=None, **kwargs):
        _ = api_partner
        rec = request.env['order_bridge.push_token'].search(
            [('device_id', '=', api_device.id)], limit=1
        )
        fcm = rec.fcm_token
        try:
            fcm_client.ensure_firebase_app()
        except fcm_client.FcmConfigurationError as e:
            return api_json_response(
                ConfigurationErrorResponse(error='configuration', message=str(e)),
                503,
            )
        for topic in body.unsubscribe_topics or []:
            if not fcm_client.unsubscribe_from_topic([fcm], topic):
                # Política: log y continuar (no 500) — mismo criterio que en subscribe
                _logger.warning(
                    'FCM unsubscribe omitido o fallido para device_id=%s topic=%r',
                    api_device.id,
                    topic,
                )
        sub_ok = _subscribed_effective(fcm, list(body.subscribe_topics or []))
        return api_json_response(
            PushTopicsOkResponse(
                status='ok',
                subscribed_topics=sub_ok,
            ),
        )
