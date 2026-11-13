# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import http
from odoo.http import request

from odoo.addons.order_bridge.schemas.responses import (
    MessageErrorResponse,
    SimpleErrorResponse,
)
from odoo.addons.order_bridge.utils.decorators import (
    api_cors_preflight,
    api_device_auth,
    api_json_response,
)
from odoo.addons.payment_gateway.providers.stripe import StripeProviderError
from odoo.addons.payment_gateway.services.currency import UnsupportedStripeCurrency
from odoo.addons.payment_gateway.services.orchestrator import (
    OrderNotPayable,
    PaymentOrchestrator,
)
from odoo.addons.payment_gateway.services.secrets import MissingStripeSecrets

_logger = logging.getLogger(__name__)


class StripePaymentController(http.Controller):
    @http.route(
        '/api/order_bridge/orders/<int:order_id>/payments/stripe',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    def start_stripe_payment(self, order_id, api_device=None, api_partner=None, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()

        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if (
            not order
            or not order.order_bridge_device_id
            or order.order_bridge_device_id.id != api_device.id
        ):
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)

        orchestrator = PaymentOrchestrator(env=request.env)
        try:
            payload = orchestrator.start_for_order(order, code='stripe')
        except OrderNotPayable as err:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(err)),
                400,
            )
        except UnsupportedStripeCurrency as err:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(err)),
                400,
            )
        except MissingStripeSecrets:
            _logger.error('Stripe secrets missing when starting payment for order %s', order_id)
            return api_json_response(
                MessageErrorResponse(
                    error='configuration',
                    message='los pagos online no están configurados',
                ),
                503,
            )
        except StripeProviderError:
            return api_json_response(
                MessageErrorResponse(
                    error='provider_error',
                    message='no se pudo iniciar el pago',
                ),
                502,
            )
        return api_json_response(payload)
