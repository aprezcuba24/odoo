# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo.fields import Command
from odoo.tests.common import HttpCase, tagged

from odoo.addons.order_bridge.utils.phone_match import phone_match_key


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
        cls.transfer = cls.env.ref('order_bridge.payment_method_transfer')
        cls.currency = cls.env.company.currency_id

    def _auth_headers(self, key=None):
        return {
            'Accept': 'application/json',
            'X-Api-Key': key if key is not None else self.api_key,
        }

    def _json_headers(self, key=None):
        headers = self._auth_headers(key)
        headers['Content-Type'] = 'application/json'
        return headers

    def _money(self, amount):
        return self.currency.format(amount)

    def _assert_payment_ok(self, payload, *, result, backend_contains=(), backend_equals=None):
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get('result'), result)
        self.assertIn('backendResponse', payload)
        self.assertIsInstance(payload['backendResponse'], str)
        if backend_equals is not None:
            self.assertEqual(payload['backendResponse'], backend_equals)
        for fragment in backend_contains:
            self.assertIn(fragment, payload['backendResponse'])
        return payload['backendResponse']

    def _create_due_order(self, *, phone='+5353024637', price=100.0, qty=1.0, name=None):
        key = phone_match_key(phone)
        partner = self.env['res.partner'].search([
            ('order_bridge_phone_key', '=', key),
            ('company_id', 'in', [False, self.env.company.id]),
        ], limit=1) if key else self.env['res.partner']
        if not partner:
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

    def test_post_payments_not_interested(self):
        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5399999999',
                'amount': 50,
                'code': 'MM-NOT-INTERESTED',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        text = self._assert_payment_ok(
            json.loads(res.text),
            result='not_interested',
            backend_contains=['Ese teléfono **no espera** un pago.'],
        )

        transfer = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM-NOT-INTERESTED'),
            ('transfer_type', '=', 'mobile'),
        ])
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.result, 'not_interested')
        self.assertEqual(transfer.backend_response, text)
        self.assertFalse(transfer.payment_ids)

        # Idempotent replay keeps stored text
        res2 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5300000000',
                'amount': 999,
                'code': 'MM-NOT-INTERESTED',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self._assert_payment_ok(
            json.loads(res2.text),
            result='not_interested',
            backend_equals=text,
        )
        self.assertEqual(
            self.env['order_bridge.transfer'].search_count([
                ('code', '=', 'MM-NOT-INTERESTED'),
            ]),
            1,
        )

    def test_post_payments_not_interested_with_partner_no_debt(self):
        partner = self.env['res.partner'].create({
            'name': 'Sin Deuda',
            'phone': '+5359011004',
        })
        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '59011004',
                'amount': 25,
                'code': 'MM-PARTNER-NO-DEBT',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        zero = self._money(0.0)
        self._assert_payment_ok(
            json.loads(res.text),
            result='not_interested',
            backend_contains=[
                'Ese teléfono **no espera** un pago.',
                f'**{partner.name}**',
                f'Deuda anterior: {zero}',
                f'Queda por pagar: {zero}',
            ],
        )

    def test_post_payments_processed_applies_to_due_orders(self):
        phone = '+5359011001'
        partner, order1 = self._create_due_order(
            phone=phone, price=60.0, name='Cliente Pagos',
        )
        _partner2, order2 = self._create_due_order(phone='59011001', price=40.0)
        self.assertEqual(partner, order2.partner_id)
        self.assertEqual(order1.order_bridge_amount_due, 60.0)
        self.assertEqual(order2.order_bridge_amount_due, 40.0)

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '59011001',
                'amount': 100,
                'code': 'MM-PROC-100',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        text = self._assert_payment_ok(
            json.loads(res.text),
            result='processed',
            backend_contains=[
                '**Pago registrado.**',
                f'**{partner.name}**',
                f'Deuda anterior: {self._money(100.0)}',
                f'Se aplicó: {self._money(100.0)}',
                f'Queda por pagar: {self._money(0.0)}',
            ],
        )
        self.assertNotIn('Sobra:', text)

        order1.invalidate_recordset()
        order2.invalidate_recordset()
        self.assertEqual(order1.order_bridge_amount_due, 0.0)
        self.assertEqual(order2.order_bridge_amount_due, 0.0)

        transfer = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM-PROC-100'),
        ])
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.result, 'processed')
        self.assertEqual(transfer.backend_response, text)
        self.assertEqual(len(transfer.payment_ids), 2)
        self.assertEqual(sum(transfer.payment_ids.mapped('amount')), 100.0)
        self.assertTrue(all(
            p.method_id == self.transfer for p in transfer.payment_ids
        ))

        # Idempotent: same code does not pay again and returns stored text
        res2 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359011001',
                'amount': 100,
                'code': 'MM-PROC-100',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self._assert_payment_ok(
            json.loads(res2.text),
            result='processed',
            backend_equals=text,
        )
        self.assertEqual(
            self.env['order_bridge.order.payment'].search_count([
                ('transfer_id', '=', transfer.id),
            ]),
            2,
        )

        # Edited backend_response is returned on next replay
        edited = 'Texto **editado** para la app.'
        transfer.write({'backend_response': edited})
        res3 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359011001',
                'amount': 100,
                'code': 'MM-PROC-100',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res3.status_code, 200, res3.text)
        self._assert_payment_ok(
            json.loads(res3.text),
            result='processed',
            backend_equals=edited,
        )
        self.assertEqual(
            self.env['order_bridge.order.payment'].search_count([
                ('transfer_id', '=', transfer.id),
            ]),
            2,
        )

    def test_post_payments_partial_across_orders(self):
        partner, order1 = self._create_due_order(
            phone='+5359011002', price=80.0, name='Cliente Parcial',
        )
        _, order2 = self._create_due_order(phone='59011002', price=50.0)
        self.assertEqual(partner, order2.partner_id)

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359011002',
                'amount': 100,
                'code': 'MM-PARTIAL-100',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self._assert_payment_ok(
            json.loads(res.text),
            result='processed',
            backend_contains=[
                '**Pago registrado.**',
                f'**{partner.name}**',
                f'Deuda anterior: {self._money(130.0)}',
                f'Se aplicó: {self._money(100.0)}',
                f'Queda por pagar: {self._money(30.0)}',
            ],
        )

        order1.invalidate_recordset()
        order2.invalidate_recordset()
        self.assertEqual(order1.order_bridge_amount_due, 0.0)
        self.assertEqual(order2.order_bridge_amount_due, 30.0)

    def test_post_payments_surplus_over_debt(self):
        partner, order = self._create_due_order(
            phone='+5359011003', price=50.0, name='Cliente Sobra',
        )
        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '59011003',
                'amount': 80,
                'code': 'MM-SURPLUS-80',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self._assert_payment_ok(
            json.loads(res.text),
            result='processed',
            backend_contains=[
                '**Pago registrado.**',
                f'**{partner.name}**',
                f'Deuda anterior: {self._money(50.0)}',
                f'Se aplicó: {self._money(50.0)}',
                f'Queda por pagar: {self._money(0.0)}',
                f'Sobra: **{self._money(30.0)}** sin aplicar.',
            ],
        )
        order.invalidate_recordset()
        self.assertEqual(order.order_bridge_amount_due, 0.0)
        transfer = self.env['order_bridge.transfer'].search([('code', '=', 'MM-SURPLUS-80')])
        self.assertEqual(len(transfer.payment_ids), 1)
        self.assertEqual(transfer.payment_ids.amount, 50.0)

    def test_deliveries_require_delivery_module(self):
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(self.no_modules.api_key),
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)
