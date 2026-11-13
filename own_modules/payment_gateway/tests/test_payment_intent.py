# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid
from unittest.mock import patch

from odoo.fields import Command
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.order_bridge.utils.constant import STATE_CANCELED
from odoo.addons.payment_gateway.providers.base import (
    PaymentEvent,
    PaymentProvider,
    PaymentStart,
)
from odoo.addons.payment_gateway.providers.registry import ProviderRegistry
from odoo.addons.payment_gateway.services.orchestrator import (
    OrderNotPayable,
    PaymentOrchestrator,
)


class RecordingStripeProvider(PaymentProvider):
    """In-memory Stripe stand-in for orchestrator tests (no HTTP)."""

    create_calls: list
    cancel_calls: list
    _seq: int

    def __init__(self):
        # Class-level lists shared across instances from the same registry get.
        pass

    def client_config(self):
        return {'publishable_key': 'pk_test_fake'}

    def start_payment(
        self,
        *,
        amount,
        currency,
        reference,
        order_id=None,
    ):
        type(self)._seq += 1
        n = type(self)._seq
        type(self).create_calls.append({
            'amount': amount,
            'currency': currency,
            'reference': reference,
            'order_id': order_id,
        })
        return PaymentStart(
            external_id=f'pi_test_{n}',
            sdk_payload={'client_secret': f'cs_test_{n}'},
        )

    def parse_webhook(self, *, payload, signature):
        return PaymentEvent(external_id='evt', status='succeeded', amount=1.0)

    def cancel_payment(self, *, external_id):
        type(self).cancel_calls.append(external_id)


def _fresh_recording_provider_cls():
    class _Provider(RecordingStripeProvider):
        create_calls = []
        cancel_calls = []
        _seq = 0

    return _Provider


@tagged('post_install', '-at_install')
class TestPaymentIntentOrchestrator(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente PaymentIntent',
            'phone': '+529991110077',
        })
        self.device = self.env['order_bridge.device'].create({
            'device_key': str(uuid.uuid4()),
            'phone': '+529991110077',
            'partner_id': self.partner.id,
            'active': True,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto PaymentIntent',
            'sale_ok': True,
            'list_price': 100.0,
            'taxes_id': [Command.clear()],
        })
        self.product = tmpl.product_variant_id
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': self.device.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
                'tax_ids': [Command.clear()],
            })],
        })
        self.Provider = _fresh_recording_provider_cls()
        self.registry = ProviderRegistry()
        self.registry.register('stripe', self.Provider)

    def _orchestrator(self):
        return PaymentOrchestrator(env=self.env, registry=self.registry)

    def test_start_marks_pending_and_creates_open_attempt(self):
        payload = self._orchestrator().start_for_order(self.order)
        self.assertEqual(payload['provider'], 'stripe')
        self.assertEqual(payload['external_id'], 'pi_test_1')
        self.assertEqual(payload['client_secret'], 'cs_test_1')
        self.assertEqual(payload['publishable_key'], 'pk_test_fake')
        self.assertEqual(payload['amount'], 100.0)
        self.assertTrue(self.order.order_bridge_payment_pending)
        self.assertEqual(self.order.order_bridge_amount_due, 100.0)
        attempt = self.env['payment_gateway.payment.attempt'].search([
            ('order_id', '=', self.order.id),
        ])
        self.assertEqual(len(attempt), 1)
        self.assertEqual(attempt.state, 'open')
        self.assertEqual(len(self.Provider.create_calls), 1)

    def test_second_start_reuses_open_attempt(self):
        first = self._orchestrator().start_for_order(self.order)
        second = self._orchestrator().start_for_order(self.order)
        self.assertEqual(first['external_id'], second['external_id'])
        self.assertEqual(len(self.Provider.create_calls), 1)
        self.assertEqual(
            self.env['payment_gateway.payment.attempt'].search_count([
                ('order_id', '=', self.order.id),
                ('state', '=', 'open'),
            ]),
            1,
        )

    def test_rejects_when_fully_paid(self):
        cash = self.env.ref('order_bridge.payment_method_cash')
        self.order.write({
            'order_bridge_payment_ids': [Command.create({
                'method_id': cash.id,
                'amount': 100.0,
            })],
        })
        with self.assertRaises(OrderNotPayable):
            self._orchestrator().start_for_order(self.order)
        self.assertFalse(self.order.order_bridge_payment_pending)
        self.assertEqual(len(self.Provider.create_calls), 0)

    def test_partial_payment_charges_remainder(self):
        cash = self.env.ref('order_bridge.payment_method_cash')
        self.order.write({
            'order_bridge_payment_pending': True,
            'order_bridge_payment_ids': [Command.create({
                'method_id': cash.id,
                'amount': 40.0,
            })],
        })
        payload = self._orchestrator().start_for_order(self.order)
        self.assertEqual(payload['amount'], 60.0)
        self.assertEqual(self.Provider.create_calls[0]['amount'], 60.0)

    def test_amount_change_cancels_and_recreates(self):
        self._orchestrator().start_for_order(self.order)
        cash = self.env.ref('order_bridge.payment_method_cash')
        self.order.write({
            'order_bridge_payment_ids': [Command.create({
                'method_id': cash.id,
                'amount': 25.0,
            })],
        })
        payload = self._orchestrator().start_for_order(self.order)
        self.assertEqual(payload['amount'], 75.0)
        self.assertEqual(payload['external_id'], 'pi_test_2')
        self.assertEqual(self.Provider.cancel_calls, ['pi_test_1'])
        self.assertEqual(len(self.Provider.create_calls), 2)
        canceled = self.env['payment_gateway.payment.attempt'].search([
            ('external_id', '=', 'pi_test_1'),
        ])
        self.assertEqual(canceled.state, 'canceled')

    def test_canceled_order_rejected(self):
        self.order.order_bridge_store_state = STATE_CANCELED
        with self.assertRaises(OrderNotPayable):
            self._orchestrator().start_for_order(self.order)


@tagged('post_install', '-at_install')
class TestPaymentIntentHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('es_ES')

    def setUp(self):
        super().setUp()
        self.device_key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({
                'phone': '60099887',
                'device_key': self.device_key,
            }),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.device = self.env['order_bridge.device'].search(
            [('device_key', '=', self.device_key)], limit=1,
        )
        tmpl = self.env['product.template'].create({
            'name': 'Producto PI HTTP',
            'sale_ok': True,
            'list_price': 80.0,
            'taxes_id': [Command.clear()],
        })
        self.product = tmpl.product_variant_id
        self.order = self.env['sale.order'].create({
            'partner_id': self.device.partner_id.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': self.device.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 80.0,
                'tax_ids': [Command.clear()],
            })],
        })
        self.Provider = _fresh_recording_provider_cls()
        self.registry = ProviderRegistry()
        self.registry.register('stripe', self.Provider)

    def _url(self, order_id=None):
        oid = self.order.id if order_id is None else order_id
        return f'/api/order_bridge/orders/{oid}/payments/stripe'

    def _post(self, *, headers=None, order_id=None):
        hdrs = {'Content-Type': 'application/json'}
        if headers:
            hdrs.update(headers)
        with patch(
            'odoo.addons.payment_gateway.controllers.stripe_payment.PaymentOrchestrator',
        ) as Orch:
            def _factory(env=None, registry=None):
                return PaymentOrchestrator(env=env, registry=self.registry)

            Orch.side_effect = _factory
            return self.url_open(
                self._url(order_id),
                data=b'{}',
                headers=hdrs,
                timeout=60,
            )

    def test_http_start_success(self):
        res = self._post(headers={'Authorization': f'Bearer {self.device_key}'})
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data['provider'], 'stripe')
        self.assertEqual(data['client_secret'], 'cs_test_1')
        self.assertEqual(data['publishable_key'], 'pk_test_fake')
        self.assertEqual(data['amount'], 80.0)
        self.order.invalidate_recordset()
        self.assertTrue(self.order.order_bridge_payment_pending)

    def test_http_unauthorized_without_bearer(self):
        res = self._post()
        self.assertEqual(res.status_code, 401, res.text)

    def test_http_other_device_not_found(self):
        other_key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011223', 'device_key': other_key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        res = self._post(headers={'Authorization': f'Bearer {other_key}'})
        self.assertEqual(res.status_code, 404, res.text)

    def test_http_fully_paid_returns_400(self):
        cash = self.env.ref('order_bridge.payment_method_cash')
        self.order.write({
            'order_bridge_payment_ids': [Command.create({
                'method_id': cash.id,
                'amount': 80.0,
            })],
        })
        res = self._post(headers={'Authorization': f'Bearer {self.device_key}'})
        self.assertEqual(res.status_code, 400, res.text)
