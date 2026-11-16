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
from odoo.addons.payment_gateway.providers.stripe import (
    StripeProviderError,
    StripeWebhookIgnoredEvent,
    StripeWebhookSignatureError,
)
from odoo.addons.payment_gateway.services.currency import UnsupportedStripeCurrency
from odoo.addons.payment_gateway.services.orchestrator import (
    OrderNotPayable,
    PaymentOrchestrator,
    UnknownPaymentAttempt,
    WebhookAmountMismatch,
)
from odoo.addons.payment_gateway.services.secrets import MissingStripeSecrets

_logger = logging.getLogger(__name__)


class StripePaymentController(http.Controller):
    def _order_for_device(self, order_id, api_device):
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if (
            not order
            or not order.order_bridge_device_id
            or order.order_bridge_device_id.id != api_device.id
        ):
            return None
        return order

    def _handle_webhook(self, *, company=None):
        payload = request.httprequest.get_data(cache=False)
        signature = request.httprequest.headers.get('Stripe-Signature') or ''

        orchestrator = PaymentOrchestrator(env=request.env)
        try:
            provider = orchestrator.provider('stripe', company=company)
            event = provider.parse_webhook(payload=payload, signature=signature)
        except MissingStripeSecrets:
            _logger.error('Stripe webhook secret missing on webhook request')
            return api_json_response(
                MessageErrorResponse(
                    error='configuration',
                    message='los pagos online no están configurados',
                ),
                503,
            )
        except StripeWebhookIgnoredEvent:
            return api_json_response({'received': True})
        except StripeWebhookSignatureError as err:
            _logger.warning('Stripe webhook rejected: %s', err)
            return api_json_response(
                MessageErrorResponse(error='invalid_signature', message=str(err)),
                400,
            )
        except UnsupportedStripeCurrency as err:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(err)),
                400,
            )

        try:
            orchestrator.apply_webhook_event(event, company=company)
        except UnknownPaymentAttempt:
            _logger.warning(
                'Stripe webhook for unknown attempt %s', event.external_id,
            )
            return api_json_response(
                MessageErrorResponse(error='not_found', message='intento no encontrado'),
                404,
            )
        except WebhookAmountMismatch as err:
            _logger.warning(
                'Stripe webhook amount mismatch for %s: %s',
                event.external_id,
                err,
            )
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(err)),
                400,
            )
        return api_json_response({'received': True})

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

        order = self._order_for_device(order_id, api_device)
        if not order:
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

    @http.route(
        '/api/order_bridge/orders/<int:order_id>/payments/stripe',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    def stripe_payment_status(self, order_id, api_device=None, api_partner=None, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()

        order = self._order_for_device(order_id, api_device)
        if not order:
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)

        orchestrator = PaymentOrchestrator(env=request.env)
        try:
            payload = orchestrator.status_for_order(order, code='stripe')
        except MissingStripeSecrets:
            _logger.error(
                'Stripe secrets missing when reading payment status for order %s',
                order_id,
            )
            return api_json_response(
                MessageErrorResponse(
                    error='configuration',
                    message='los pagos online no están configurados',
                ),
                503,
            )
        return api_json_response(payload)

    @http.route(
        '/api/payment_gateway/stripe/webhook',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def stripe_webhook(self, **kwargs):
        """Webhook without slug: credentials of ``base.main_company``."""
        company = request.env.ref('base.main_company').sudo()
        return self._handle_webhook(company=company)

    @http.route(
        '/api/payment_gateway/stripe/webhook/<string:slug>',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def stripe_webhook_for_company(self, slug, **kwargs):
        """Webhook with slug: credentials of the company identified by slug."""
        company = request.env['res.company'].sudo()._order_bridge_find_by_slug(slug)
        if not company:
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return self._handle_webhook(company=company)
