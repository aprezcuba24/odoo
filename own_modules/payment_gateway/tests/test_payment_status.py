# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid
from unittest.mock import patch

from odoo.fields import Command
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.payment_gateway.providers.registry import ProviderRegistry
from odoo.addons.payment_gateway.services.orchestrator import PaymentOrchestrator
from odoo.addons.payment_gateway.tests.test_payment_intent import (
    _fresh_recording_provider_cls,
)


@tagged('post_install', '-at_install')
class TestPaymentStatusOrchestrator(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente PaymentStatus',
            'phone': '+529991110088',
        })
        self.device = self.env['order_bridge.device'].create({
            'device_key': str(uuid.uuid4()),
            'phone': '+529991110088',
            'partner_id': self.partner.id,
            'active': True,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto PaymentStatus',
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

    def test_status_without_attempt(self):
        payload = self._orchestrator().status_for_order(self.order)
        self.assertEqual(payload['provider'], 'stripe')
        self.assertEqual(payload['amount_paid'], 0.0)
        self.assertEqual(payload['amount_due'], 0.0)
        self.assertIsNone(payload['attempt'])
        self.assertFalse(payload.get('client_secret'))

    def test_status_open_includes_client_secret(self):
        self._orchestrator().start_for_order(self.order)
        payload = self._orchestrator().status_for_order(self.order)
        self.assertEqual(payload['amount_paid'], 0.0)
        self.assertEqual(payload['amount_due'], 100.0)
        attempt = payload['attempt']
        self.assertEqual(attempt['state'], 'open')
        self.assertEqual(attempt['external_id'], 'pi_test_1')
        self.assertEqual(attempt['amount'], 100.0)
        self.assertEqual(attempt['client_secret'], 'cs_test_1')
        self.assertEqual(attempt['publishable_key'], 'pk_test_fake')

    def test_status_succeeded_hides_client_secret(self):
        self._orchestrator().start_for_order(self.order)
        attempt = self.env['payment_gateway.payment.attempt'].search([
            ('order_id', '=', self.order.id),
        ], limit=1)
        method = self.env.ref('payment_gateway.payment_method_stripe')
        self.env['order_bridge.order.payment'].create({
            'order_id': self.order.id,
            'method_id': method.id,
            'amount': 100.0,
        })
        attempt.write({'state': 'succeeded'})
        self.order.invalidate_recordset()
        payload = self._orchestrator().status_for_order(self.order)
        self.assertEqual(payload['amount_paid'], 100.0)
        self.assertEqual(payload['amount_due'], 0.0)
        self.assertEqual(payload['attempt']['state'], 'succeeded')
        self.assertEqual(payload['attempt']['external_id'], 'pi_test_1')
        self.assertNotIn('client_secret', payload['attempt'])
        self.assertNotIn('publishable_key', payload['attempt'])

    def test_status_failed_hides_client_secret(self):
        self._orchestrator().start_for_order(self.order)
        attempt = self.env['payment_gateway.payment.attempt'].search([
            ('order_id', '=', self.order.id),
        ], limit=1)
        attempt.write({'state': 'failed'})
        self.order.invalidate_recordset()
        payload = self._orchestrator().status_for_order(self.order)
        self.assertEqual(payload['amount_paid'], 0.0)
        self.assertEqual(payload['amount_due'], 100.0)
        self.assertEqual(payload['attempt']['state'], 'failed')
        self.assertNotIn('client_secret', payload['attempt'])
        self.assertNotIn('publishable_key', payload['attempt'])


@tagged('post_install', '-at_install')
class TestPaymentStatusHttp(HttpCase):
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
                'phone': '60099889',
                'device_key': self.device_key,
            }),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.device = self.env['order_bridge.device'].search(
            [('device_key', '=', self.device_key)], limit=1,
        )
        tmpl = self.env['product.template'].create({
            'name': 'Producto Status HTTP',
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

    def _get(self, *, headers=None, order_id=None):
        hdrs = {}
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
                headers=hdrs,
                timeout=60,
            )

    def _post_start(self):
        with patch(
            'odoo.addons.payment_gateway.controllers.stripe_payment.PaymentOrchestrator',
        ) as Orch:
            def _factory(env=None, registry=None):
                return PaymentOrchestrator(env=env, registry=self.registry)

            Orch.side_effect = _factory
            return self.url_open(
                self._url(),
                data=b'{}',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.device_key}',
                },
                timeout=60,
            )

    def test_http_status_without_attempt(self):
        res = self._get(headers={'Authorization': f'Bearer {self.device_key}'})
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data['amount_paid'], 0.0)
        self.assertEqual(data['amount_due'], 0.0)
        self.assertIsNone(data['attempt'])

    def test_http_status_open(self):
        start = self._post_start()
        self.assertEqual(start.status_code, 200, start.text)
        res = self._get(headers={'Authorization': f'Bearer {self.device_key}'})
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data['amount_due'], 80.0)
        self.assertEqual(data['attempt']['state'], 'open')
        self.assertEqual(data['attempt']['client_secret'], 'cs_test_1')
        self.assertEqual(data['attempt']['publishable_key'], 'pk_test_fake')

    def test_http_unauthorized_without_bearer(self):
        res = self._get()
        self.assertEqual(res.status_code, 401, res.text)

    def test_http_other_device_not_found(self):
        other_key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011224', 'device_key': other_key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        res = self._get(headers={'Authorization': f'Bearer {other_key}'})
        self.assertEqual(res.status_code, 404, res.text)
