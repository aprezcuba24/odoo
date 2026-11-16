# Part of Odoo. See LICENSE file for full copyright and licensing details.

import os
from unittest.mock import patch

from odoo.fields import Command
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.payment_gateway.providers.registry import ProviderRegistry
from odoo.addons.payment_gateway.providers.stripe import StripeProvider
from odoo.addons.payment_gateway.services.currency import to_stripe_minor_units
from odoo.addons.payment_gateway.services.orchestrator import PaymentOrchestrator
from odoo.addons.payment_gateway.services.secrets import (
    MissingStripeSecrets,
    credentials_for_company,
)
from odoo.addons.payment_gateway.tests.common import enable_payment_gateway_app


class _FakePaymentIntent:
    last_create = None
    last_api_key = None

    @classmethod
    def create(cls, **kwargs):
        cls.last_create = kwargs
        cls.last_api_key = kwargs.get('api_key')
        return {'id': 'pi_company_a', 'client_secret': 'cs_company_a'}

    @classmethod
    def cancel(cls, external_id, **kwargs):
        return {'id': external_id, 'status': 'canceled'}


class _FakeStripeClient:
    PaymentIntent = _FakePaymentIntent


def _stripe_cls_with_client_and_construct(construct=None):
    class _Provider(StripeProvider):
        def __init__(self, credentials=None, **kwargs):
            super().__init__(
                client=_FakeStripeClient,
                webhook_construct=construct,
                credentials=credentials,
            )

    return _Provider


@tagged('post_install', '-at_install')
class TestStripeCredentialsResolution(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company_a = self.env['res.company'].create({
            'name': 'Tienda Secrets A',
            'order_bridge_slug': 'secrets-a',
        })
        self.company_b = self.env['res.company'].create({
            'name': 'Tienda Secrets B',
            'order_bridge_slug': 'secrets-b',
        })
        enable_payment_gateway_app(self.env, self.company_a, self.company_b)
        self.env['payment_gateway.stripe.account'].create({
            'company_id': self.company_a.id,
            'secret_key': 'sk_test_a',
            'publishable_key': 'pk_test_a',
            'webhook_secret': 'whsec_a',
        })
        self.env['payment_gateway.stripe.account'].create({
            'company_id': self.company_b.id,
            'secret_key': 'sk_test_b',
            'publishable_key': 'pk_test_b',
            'webhook_secret': 'whsec_b',
        })

    def test_credentials_for_company_uses_row(self):
        creds = credentials_for_company(self.env, self.company_a)
        self.assertEqual(creds.secret_key, 'sk_test_a')
        self.assertEqual(creds.publishable_key, 'pk_test_a')
        self.assertEqual(creds.webhook_secret, 'whsec_a')

    def test_without_row_raises(self):
        orphan = self.env['res.company'].create({
            'name': 'Sin Stripe',
            'order_bridge_slug': 'secrets-orphan',
        })
        with self.assertRaises(MissingStripeSecrets):
            credentials_for_company(self.env, orphan)

    def test_incomplete_row_raises(self):
        company = self.env['res.company'].create({
            'name': 'Stripe Incompleto',
            'order_bridge_slug': 'secrets-incomplete',
        })
        enable_payment_gateway_app(self.env, company)
        self.env['payment_gateway.stripe.account'].create({
            'company_id': company.id,
            'secret_key': 'sk_only',
            'publishable_key': '',
            'webhook_secret': '',
        })
        with self.assertRaises(MissingStripeSecrets):
            credentials_for_company(self.env, company)

    def test_env_vars_are_ignored(self):
        orphan = self.env['res.company'].create({
            'name': 'Sin Fila Env',
            'order_bridge_slug': 'secrets-no-env',
        })
        with patch.dict(os.environ, {
            'STRIPE_SECRET_KEY': 'sk_env',
            'STRIPE_PUBLISHABLE_KEY': 'pk_env',
            'STRIPE_WEBHOOK_SECRET': 'whsec_env',
        }, clear=False):
            with self.assertRaises(MissingStripeSecrets):
                credentials_for_company(self.env, orphan)

    def test_start_for_order_uses_company_secret(self):
        _FakePaymentIntent.last_create = None
        partner = self.env['res.partner'].create({
            'name': 'Cliente Secrets A',
            'phone': '+529991110201',
            'company_id': self.company_a.id,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto Secrets A',
            'sale_ok': True,
            'list_price': 10.0,
            'taxes_id': [Command.clear()],
            'company_id': self.company_a.id,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': self.company_a.id,
            'currency_id': self.env.ref('base.USD').id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': tmpl.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 10.0,
                'tax_ids': [Command.clear()],
            })],
        })
        registry = ProviderRegistry()
        registry.register('stripe', _stripe_cls_with_client_and_construct())
        orch = PaymentOrchestrator(env=self.env, registry=registry)
        payload = orch.start_for_order(order)
        self.assertEqual(payload['publishable_key'], 'pk_test_a')
        self.assertEqual(_FakePaymentIntent.last_api_key, 'sk_test_a')


@tagged('post_install', '-at_install')
class TestStripeWebhookPerCompany(HttpCase):
    def setUp(self):
        super().setUp()
        self.company_a = self.env['res.company'].create({
            'name': 'Webhook Co A',
            'order_bridge_slug': 'wh-co-a',
        })
        self.company_b = self.env['res.company'].create({
            'name': 'Webhook Co B',
            'order_bridge_slug': 'wh-co-b',
        })
        enable_payment_gateway_app(self.env, self.company_a, self.company_b)
        self.env['payment_gateway.stripe.account'].create({
            'company_id': self.company_a.id,
            'secret_key': 'sk_a',
            'publishable_key': 'pk_a',
            'webhook_secret': 'whsec_a',
        })
        self.env['payment_gateway.stripe.account'].create({
            'company_id': self.company_b.id,
            'secret_key': 'sk_b',
            'publishable_key': 'pk_b',
            'webhook_secret': 'whsec_b',
        })
        usd = self.env.ref('base.USD')
        partner = self.env['res.partner'].create({
            'name': 'Cliente WH A',
            'phone': '+529991110202',
            'company_id': self.company_a.id,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto WH A',
            'sale_ok': True,
            'list_price': 30.0,
            'taxes_id': [Command.clear()],
            'company_id': self.company_a.id,
        })
        self.order_a = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': self.company_a.id,
            'currency_id': usd.id,
            'order_bridge_origin': 'app',
            'order_bridge_payment_pending': True,
            'order_line': [Command.create({
                'product_id': tmpl.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 30.0,
                'tax_ids': [Command.clear()],
            })],
        })
        self.attempt_a = self.env['payment_gateway.payment.attempt'].create({
            'order_id': self.order_a.id,
            'provider_code': 'stripe',
            'external_id': 'pi_wh_a',
            'client_secret': 'cs_wh_a',
            'state': 'open',
            'amount': 30.0,
            'currency_id': usd.id,
        })

    def _event(self, external_id='pi_wh_a', amount=30.0):
        return {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': external_id,
                    'amount': to_stripe_minor_units(amount, 'usd'),
                    'currency': 'usd',
                },
            },
        }

    def _post(self, slug, *, expected_secret, event=None, signature='t=1,v1=ok'):
        if event is None:
            event = self._event()
        seen = {}

        def construct(payload, sig, secret):
            seen['secret'] = secret
            if secret != expected_secret:
                raise ValueError('wrong secret')
            return event

        test_registry = ProviderRegistry()
        test_registry.register('stripe', _stripe_cls_with_client_and_construct(construct))

        with patch(
            'odoo.addons.payment_gateway.controllers.stripe_payment.PaymentOrchestrator',
        ) as Orch:
            def _factory(env=None, registry=None):
                return PaymentOrchestrator(env=env, registry=test_registry)

            Orch.side_effect = _factory
            with patch.dict(os.environ, {'ODOO_MULTI_COMPANY_S3': 'true'}, clear=False):
                res = self.url_open(
                    f'/api/payment_gateway/stripe/webhook/{slug}',
                    data=b'{"id":"evt_1"}',
                    headers={
                        'Content-Type': 'application/json',
                        'Stripe-Signature': signature,
                    },
                    timeout=60,
                )
        return res, seen

    def test_webhook_slug_b_accepts_secret_b(self):
        partner_b = self.env['res.partner'].create({
            'name': 'Cliente WH B',
            'phone': '+529991110203',
            'company_id': self.company_b.id,
        })
        tmpl_b = self.env['product.template'].create({
            'name': 'Producto WH B',
            'sale_ok': True,
            'list_price': 30.0,
            'taxes_id': [Command.clear()],
            'company_id': self.company_b.id,
        })
        order_b = self.env['sale.order'].create({
            'partner_id': partner_b.id,
            'company_id': self.company_b.id,
            'currency_id': self.env.ref('base.USD').id,
            'order_bridge_origin': 'app',
            'order_bridge_payment_pending': True,
            'order_line': [Command.create({
                'product_id': tmpl_b.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 30.0,
                'tax_ids': [Command.clear()],
            })],
        })
        attempt_b = self.env['payment_gateway.payment.attempt'].create({
            'order_id': order_b.id,
            'provider_code': 'stripe',
            'external_id': 'pi_wh_b',
            'client_secret': 'cs_wh_b',
            'state': 'open',
            'amount': 30.0,
            'currency_id': self.env.ref('base.USD').id,
        })
        res, seen = self._post(
            'wh-co-b',
            expected_secret='whsec_b',
            event=self._event(external_id='pi_wh_b'),
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(seen.get('secret'), 'whsec_b')
        attempt_b.invalidate_recordset()
        self.assertEqual(attempt_b.state, 'succeeded')

    def test_webhook_slug_b_rejects_secret_a(self):
        # Verifier only accepts company A's signing secret; slug B supplies
        # whsec_b, so signature verification must fail.
        def construct_a_only(payload, sig, secret):
            if secret != 'whsec_a':
                raise ValueError('not a')
            return self._event(external_id='pi_wh_b')

        test_registry = ProviderRegistry()
        test_registry.register(
            'stripe',
            _stripe_cls_with_client_and_construct(construct_a_only),
        )
        with patch(
            'odoo.addons.payment_gateway.controllers.stripe_payment.PaymentOrchestrator',
        ) as Orch:
            def _factory(env=None, registry=None):
                return PaymentOrchestrator(env=env, registry=test_registry)

            Orch.side_effect = _factory
            with patch.dict(os.environ, {'ODOO_MULTI_COMPANY_S3': 'true'}, clear=False):
                res = self.url_open(
                    '/api/payment_gateway/stripe/webhook/wh-co-b',
                    data=b'{}',
                    headers={
                        'Content-Type': 'application/json',
                        'Stripe-Signature': 't=1,v1=x',
                    },
                    timeout=60,
                )
        self.assertEqual(res.status_code, 400, res.text)

    def test_attempt_of_a_on_slug_b_is_404(self):
        res, seen = self._post(
            'wh-co-b',
            expected_secret='whsec_b',
            event=self._event(external_id='pi_wh_a'),
        )
        self.assertEqual(res.status_code, 404, res.text)
        self.assertEqual(seen.get('secret'), 'whsec_b')
        self.attempt_a.invalidate_recordset()
        self.assertEqual(self.attempt_a.state, 'open')
        self.order_a.invalidate_recordset()
        self.assertFalse(self.order_a.order_bridge_payment_ids)

    def test_unknown_slug_404(self):
        with patch.dict(os.environ, {'ODOO_MULTI_COMPANY_S3': 'true'}, clear=False):
            res = self.url_open(
                '/api/payment_gateway/stripe/webhook/slug-inexistente',
                data=b'{}',
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 't=1,v1=x',
                },
                timeout=60,
            )
        self.assertEqual(res.status_code, 404, res.text)
