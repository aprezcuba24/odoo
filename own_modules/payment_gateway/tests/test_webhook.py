# Part of Odoo. See LICENSE file for full copyright and licensing details.

import os
from unittest.mock import patch

from odoo.fields import Command
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.payment_gateway.providers.base import PaymentEvent
from odoo.addons.payment_gateway.providers.registry import ProviderRegistry
from odoo.addons.payment_gateway.providers.stripe import (
    StripeProvider,
    StripeWebhookSignatureError,
)
from odoo.addons.payment_gateway.services.currency import to_stripe_minor_units
from odoo.addons.payment_gateway.services.orchestrator import (
    PaymentOrchestrator,
    UnknownPaymentAttempt,
    WebhookAmountMismatch,
)


def _provider_cls_with_construct(construct):
    class _Provider(StripeProvider):
        def __init__(self):
            super().__init__(webhook_construct=construct)

    return _Provider


@tagged('post_install', '-at_install')
class TestWebhookOrchestrator(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Webhook',
            'phone': '+529991110099',
        })
        usd = self.env.ref('base.USD')
        tmpl = self.env['product.template'].create({
            'name': 'Producto Webhook',
            'sale_ok': True,
            'list_price': 50.0,
            'taxes_id': [Command.clear()],
        })
        self.product = tmpl.product_variant_id
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'currency_id': usd.id,
            'order_bridge_origin': 'app',
            'order_bridge_payment_pending': True,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 50.0,
                'tax_ids': [Command.clear()],
            })],
        })
        self.attempt = self.env['payment_gateway.payment.attempt'].create({
            'order_id': self.order.id,
            'provider_code': 'stripe',
            'external_id': 'pi_webhook_1',
            'client_secret': 'cs_webhook_1',
            'state': 'open',
            'amount': 50.0,
            'currency_id': usd.id,
        })
        self.orchestrator = PaymentOrchestrator(env=self.env)

    def test_succeeded_creates_one_payment_line(self):
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='succeeded',
            amount=50.0,
        )
        self.orchestrator.apply_webhook_event(event)
        self.attempt.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'succeeded')
        payments = self.order.order_bridge_payment_ids
        self.assertEqual(len(payments), 1)
        stripe_method = self.env.ref('payment_gateway.payment_method_stripe')
        self.assertEqual(payments.method_id, stripe_method)
        self.assertEqual(payments.amount, 50.0)

    def test_succeeded_retry_is_idempotent(self):
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='succeeded',
            amount=50.0,
        )
        self.orchestrator.apply_webhook_event(event)
        self.orchestrator.apply_webhook_event(event)
        self.order.invalidate_recordset()
        self.assertEqual(len(self.order.order_bridge_payment_ids), 1)

    def test_failed_updates_state_without_payment(self):
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='failed',
            amount=50.0,
        )
        self.orchestrator.apply_webhook_event(event)
        self.attempt.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'failed')
        self.assertFalse(self.order.order_bridge_payment_ids)

    def test_failed_does_not_downgrade_succeeded(self):
        self.attempt.write({'state': 'succeeded'})
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='failed',
            amount=50.0,
        )
        self.orchestrator.apply_webhook_event(event)
        self.attempt.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'succeeded')

    def test_unknown_attempt_raises(self):
        event = PaymentEvent(
            external_id='pi_missing',
            status='succeeded',
            amount=50.0,
        )
        with self.assertRaises(UnknownPaymentAttempt):
            self.orchestrator.apply_webhook_event(event)

    def test_amount_mismatch_raises(self):
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='succeeded',
            amount=40.0,
        )
        with self.assertRaises(WebhookAmountMismatch):
            self.orchestrator.apply_webhook_event(event)
        self.attempt.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'open')
        self.assertFalse(self.order.order_bridge_payment_ids)

    def test_canceled_attempt_ignores_succeeded(self):
        self.attempt.write({'state': 'canceled'})
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='succeeded',
            amount=50.0,
        )
        self.orchestrator.apply_webhook_event(event)
        self.order.invalidate_recordset()
        self.assertFalse(self.order.order_bridge_payment_ids)
        self.attempt.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'canceled')

    def test_succeeded_after_failed_creates_payment(self):
        self.attempt.write({'state': 'failed'})
        event = PaymentEvent(
            external_id='pi_webhook_1',
            status='succeeded',
            amount=50.0,
        )
        self.orchestrator.apply_webhook_event(event)
        self.attempt.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'succeeded')
        self.assertEqual(len(self.order.order_bridge_payment_ids), 1)


@tagged('post_install', '-at_install')
class TestWebhookHttp(HttpCase):
    def setUp(self):
        super().setUp()
        self.env_patch = patch.dict(os.environ, {
            'STRIPE_SECRET_KEY': 'sk_test_http',
            'STRIPE_PUBLISHABLE_KEY': 'pk_test_http',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test_http',
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Webhook HTTP',
            'phone': '+529991110100',
        })
        usd = self.env.ref('base.USD')
        tmpl = self.env['product.template'].create({
            'name': 'Producto Webhook HTTP',
            'sale_ok': True,
            'list_price': 25.0,
            'taxes_id': [Command.clear()],
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'currency_id': usd.id,
            'order_bridge_origin': 'app',
            'order_bridge_payment_pending': True,
            'order_line': [Command.create({
                'product_id': tmpl.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 25.0,
                'tax_ids': [Command.clear()],
            })],
        })
        self.attempt = self.env['payment_gateway.payment.attempt'].create({
            'order_id': self.order.id,
            'provider_code': 'stripe',
            'external_id': 'pi_http_1',
            'client_secret': 'cs_http_1',
            'state': 'open',
            'amount': 25.0,
            'currency_id': usd.id,
        })
        self.currency_code = 'usd'

    def _default_event(self, external_id='pi_http_1', amount=25.0):
        return {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': external_id,
                    'amount': to_stripe_minor_units(amount, self.currency_code),
                    'currency': self.currency_code,
                },
            },
        }

    def _post_webhook(self, *, construct_side_effect=None, event=None, signature='t=1,v1=ok'):
        if event is None:
            event = self._default_event()

        def construct(payload, sig, secret):
            if construct_side_effect is not None:
                return construct_side_effect(payload, sig, secret)
            return event

        test_registry = ProviderRegistry()
        test_registry.register('stripe', _provider_cls_with_construct(construct))

        with patch(
            'odoo.addons.payment_gateway.controllers.stripe_payment.PaymentOrchestrator',
        ) as Orch:
            def _factory(env=None, registry=None):
                return PaymentOrchestrator(env=env, registry=test_registry)

            Orch.side_effect = _factory
            return self.url_open(
                '/api/payment_gateway/stripe/webhook',
                data=b'{"id":"evt_1"}',
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': signature,
                },
                timeout=60,
            )

    def test_http_succeeded_200(self):
        res = self._post_webhook()
        self.assertEqual(res.status_code, 200, res.text)
        self.attempt.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'succeeded')
        self.assertEqual(len(self.order.order_bridge_payment_ids), 1)

    def test_http_invalid_signature_400(self):
        def bad(payload, sig, secret):
            raise StripeWebhookSignatureError('bad')

        res = self._post_webhook(construct_side_effect=bad)
        self.assertEqual(res.status_code, 400, res.text)

    def test_http_ignored_event_200(self):
        event = {
            'type': 'charge.updated',
            'data': {
                'object': {
                    'id': 'ch_1',
                    'amount': 2500,
                    'currency': 'usd',
                },
            },
        }
        res = self._post_webhook(event=event)
        self.assertEqual(res.status_code, 200, res.text)
        self.attempt.invalidate_recordset()
        self.assertEqual(self.attempt.state, 'open')

    def test_http_unknown_attempt_404(self):
        res = self._post_webhook(event=self._default_event(external_id='pi_unknown'))
        self.assertEqual(res.status_code, 404, res.text)

    def test_http_missing_secret_503(self):
        with patch.dict(os.environ, {'STRIPE_WEBHOOK_SECRET': ''}, clear=False):
            registry = ProviderRegistry()
            registry.register('stripe', StripeProvider)
            with patch(
                'odoo.addons.payment_gateway.controllers.stripe_payment.PaymentOrchestrator',
            ) as Orch:
                def _factory(env=None, registry=None):
                    return PaymentOrchestrator(env=env, registry=registry)

                Orch.side_effect = _factory
                res = self.url_open(
                    '/api/payment_gateway/stripe/webhook',
                    data=b'{}',
                    headers={
                        'Content-Type': 'application/json',
                        'Stripe-Signature': 't=1,v1=x',
                    },
                    timeout=60,
                )
        self.assertEqual(res.status_code, 503, res.text)
