# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo.fields import Command
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestMobileModulesPaymentsApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('es_ES')
        cls.messenger = cls.env['order_bridge.messenger'].create({
            'name': 'Mensajero pagos',
            'module_delivery': True,
            'module_payments': True,
        })
        cls.api_key = cls.messenger.api_key
        cls.delivery_only = cls.env['order_bridge.messenger'].create({
            'name': 'Solo entregas',
            'module_delivery': True,
            'module_payments': False,
        })
        cls.no_modules = cls.env['order_bridge.messenger'].create({
            'name': 'Sin módulos',
            'module_delivery': False,
            'module_payments': False,
        })

    def _auth_headers(self, key=None):
        return {
            'Accept': 'application/json',
            'X-Api-Key': key if key is not None else self.api_key,
        }

    def _json_headers(self, key=None):
        headers = self._auth_headers(key)
        headers['Content-Type'] = 'application/json'
        return headers

    def _assert_payment_ok(self, payload, *, result='processed', backend_equals=''):
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get('result'), result)
        self.assertIn('backendResponse', payload)
        self.assertIsInstance(payload['backendResponse'], str)
        self.assertEqual(payload['backendResponse'], backend_equals)
        return payload['backendResponse']

    def _create_due_order(self, *, phone='+5359012001', price=100.0, qty=1.0, name=None):
        partner = self.env['res.partner'].create({
            'name': name or f'Cliente {phone}',
            'phone': phone,
        })
        product = self.env['product.product'].create({
            'name': f'Prod {phone}-{price}',
            'sale_ok': True,
            'list_price': price,
            'taxes_id': [Command.clear()],
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_payment_pending': True,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price,
                'tax_ids': [Command.clear()],
            })],
        })
        return partner, order

    def test_get_modules_requires_api_key(self):
        res = self.url_open(
            '/api/mobile/v1/modules',
            headers={'Accept': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)
        self.assertEqual(json.loads(res.text), {'error': 'unauthorized'})

        res_bad = self.url_open(
            '/api/mobile/v1/modules',
            headers=self._auth_headers('bad-key'),
            timeout=60,
        )
        self.assertEqual(res_bad.status_code, 401, res_bad.text)

    def test_get_modules_returns_granted_ids(self):
        res = self.url_open(
            '/api/mobile/v1/modules',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(
            data,
            {'modules': [{'id': 'delivery'}, {'id': 'payments'}]},
        )

    def test_get_modules_empty_list(self):
        res = self.url_open(
            '/api/mobile/v1/modules',
            headers=self._auth_headers(self.no_modules.api_key),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(json.loads(res.text), {'modules': []})

    def test_post_payments_requires_payments_module(self):
        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '53024637',
                'amount': 10,
                'code': 'CODE-NO-MODULE',
            }),
            headers=self._json_headers(self.delivery_only.api_key),
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)
        self.assertEqual(json.loads(res.text), {'error': 'unauthorized'})
        self.assertNotIn('backendResponse', json.loads(res.text))

    def test_post_payments_validation_errors(self):
        cases = [
            ('not-json', 'invalid_body'),
            (json.dumps([]), 'invalid_body'),
            (json.dumps({'amount': 1, 'code': 'X'}), 'invalid_phone'),
            (json.dumps({'phone': '   ', 'amount': 1, 'code': 'X'}), 'invalid_phone'),
            (json.dumps({'phone': '53024637', 'amount': 0, 'code': 'X'}), 'invalid_amount'),
            (json.dumps({'phone': '53024637', 'amount': '10', 'code': 'X'}), 'invalid_amount'),
            (json.dumps({'phone': '53024637', 'amount': True, 'code': 'X'}), 'invalid_amount'),
            (json.dumps({'phone': '53024637', 'amount': 10, 'code': '  '}), 'invalid_code'),
        ]
        for body, error in cases:
            res = self.url_open(
                '/api/mobile/v1/payments',
                data=body,
                headers=self._json_headers(),
                timeout=60,
            )
            self.assertEqual(res.status_code, 400, body)
            payload = json.loads(res.text)
            self.assertEqual(payload, {'error': error}, body)
            self.assertNotIn('backendResponse', payload)

    def test_post_payments_registers_unknown_phone_without_applying(self):
        partner, order = self._create_due_order(
            phone='+5359012001', price=100.0, name='Cliente con deuda',
        )
        due_before = order.order_bridge_amount_due

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5399999999',
                'amount': 50,
                'code': 'MM-UNKNOWN-PHONE',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self._assert_payment_ok(json.loads(res.text), result='processed', backend_equals='')

        transfer = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM-UNKNOWN-PHONE'),
            ('transfer_type', '=', 'mobile'),
        ])
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.result, 'processed')
        self.assertFalse(transfer.applied)
        self.assertEqual(transfer.phone, '5399999999')
        self.assertFalse(transfer.partner_id)
        self.assertFalse(transfer.payment_ids)
        self.assertEqual(transfer.messenger_id, self.messenger)

        order.invalidate_recordset()
        self.assertEqual(order.order_bridge_amount_due, due_before)
        self.assertEqual(partner.order_bridge_amount_due, due_before)

    def test_post_payments_idempotent_same_code(self):
        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012002',
                'amount': 25,
                'code': 'MM-IDEM-001',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self._assert_payment_ok(json.loads(res.text))

        res2 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5300000000',
                'amount': 999,
                'code': 'MM-IDEM-001',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self._assert_payment_ok(json.loads(res2.text))

        transfers = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM-IDEM-001'),
        ])
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers.phone, '5359012002')
        self.assertEqual(transfers.amount, 25.0)
        self.assertFalse(transfers.payment_ids)

    def test_post_payments_matching_phone_still_does_not_apply(self):
        partner, order = self._create_due_order(
            phone='+5359012003', price=80.0, name='Cliente coincidente',
        )
        due_before = order.order_bridge_amount_due

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '59012003',
                'amount': 40,
                'code': 'MM-MATCH-NO-APPLY',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self._assert_payment_ok(json.loads(res.text))

        transfer = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM-MATCH-NO-APPLY'),
        ])
        self.assertEqual(len(transfer), 1)
        self.assertFalse(transfer.payment_ids)
        self.assertFalse(transfer.partner_id)

        order.invalidate_recordset()
        partner.invalidate_recordset()
        self.assertEqual(order.order_bridge_amount_due, due_before)
        self.assertEqual(partner.order_bridge_amount_due, due_before)

    def test_deliveries_require_delivery_module(self):
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(self.no_modules.api_key),
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)
