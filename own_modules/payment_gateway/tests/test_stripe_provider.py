# Part of Odoo. See LICENSE file for full copyright and licensing details.

import os
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.payment_gateway.providers.stripe import (
    StripeProvider,
    StripeWebhookIgnoredEvent,
    StripeWebhookSignatureError,
)


class _FakePaymentIntent:
    last_create = None
    last_cancel = None

    @classmethod
    def create(cls, **kwargs):
        cls.last_create = kwargs
        return {'id': 'pi_fake_1', 'client_secret': 'cs_fake_1'}

    @classmethod
    def cancel(cls, external_id, **kwargs):
        cls.last_cancel = (external_id, kwargs)
        return {'id': external_id, 'status': 'canceled'}


class _FakeStripeClient:
    PaymentIntent = _FakePaymentIntent


@tagged('post_install', '-at_install')
class TestStripeProvider(TransactionCase):
    def setUp(self):
        super().setUp()
        _FakePaymentIntent.last_create = None
        _FakePaymentIntent.last_cancel = None
        self.env_patch = patch.dict(os.environ, {
            'STRIPE_SECRET_KEY': 'sk_test_unit',
            'STRIPE_PUBLISHABLE_KEY': 'pk_test_unit',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test_unit',
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.provider = StripeProvider(client=_FakeStripeClient)

    def test_start_payment_builds_intent_kwargs(self):
        start = self.provider.start_payment(
            amount=12.34,
            currency='usd',
            reference='SO001',
            order_id=99,
        )
        self.assertEqual(start.external_id, 'pi_fake_1')
        self.assertEqual(start.sdk_payload['client_secret'], 'cs_fake_1')
        created = _FakePaymentIntent.last_create
        self.assertEqual(created['amount'], 1234)
        self.assertEqual(created['currency'], 'usd')
        self.assertEqual(created['payment_method_types'], ['card'])
        self.assertEqual(created['metadata']['order_id'], '99')
        self.assertEqual(created['metadata']['reference'], 'SO001')
        self.assertEqual(created['idempotency_key'], 'pgw-99-1234-usd')
        self.assertEqual(created['api_key'], 'sk_test_unit')

    def test_client_config_returns_publishable_key(self):
        self.assertEqual(
            self.provider.client_config(),
            {'publishable_key': 'pk_test_unit'},
        )

    def test_cancel_payment(self):
        self.provider.cancel_payment(external_id='pi_fake_1')
        self.assertEqual(_FakePaymentIntent.last_cancel[0], 'pi_fake_1')

    def test_parse_webhook_succeeded(self):
        def construct(payload, signature, secret):
            self.assertEqual(payload, b'{"ok":1}')
            self.assertEqual(signature, 't=1,v1=abc')
            self.assertEqual(secret, 'whsec_test_unit')
            return {
                'type': 'payment_intent.succeeded',
                'data': {
                    'object': {
                        'id': 'pi_ok',
                        'amount': 1234,
                        'currency': 'usd',
                    },
                },
            }

        provider = StripeProvider(
            client=_FakeStripeClient,
            webhook_construct=construct,
        )
        event = provider.parse_webhook(payload=b'{"ok":1}', signature='t=1,v1=abc')
        self.assertEqual(event.external_id, 'pi_ok')
        self.assertEqual(event.status, 'succeeded')
        self.assertEqual(event.amount, 12.34)

    def test_parse_webhook_payment_failed(self):
        def construct(payload, signature, secret):
            return {
                'type': 'payment_intent.payment_failed',
                'data': {
                    'object': {
                        'id': 'pi_fail',
                        'amount': 500,
                        'currency': 'eur',
                    },
                },
            }

        provider = StripeProvider(webhook_construct=construct)
        event = provider.parse_webhook(payload=b'{}', signature='sig')
        self.assertEqual(event.status, 'failed')
        self.assertEqual(event.external_id, 'pi_fail')
        self.assertEqual(event.amount, 5.0)

    def test_parse_webhook_ignored_event(self):
        def construct(payload, signature, secret):
            return {
                'type': 'charge.refunded',
                'data': {'object': {'id': 'ch_1', 'amount': 100, 'currency': 'usd'}},
            }

        provider = StripeProvider(webhook_construct=construct)
        with self.assertRaises(StripeWebhookIgnoredEvent):
            provider.parse_webhook(payload=b'{}', signature='sig')

    def test_parse_webhook_bad_signature(self):
        def construct(payload, signature, secret):
            raise ValueError('bad sig')

        provider = StripeProvider(webhook_construct=construct)
        with self.assertRaises(StripeWebhookSignatureError):
            provider.parse_webhook(payload=b'{}', signature='sig')

    def test_parse_webhook_missing_signature(self):
        with self.assertRaises(StripeWebhookSignatureError):
            self.provider.parse_webhook(payload=b'{}', signature='')
