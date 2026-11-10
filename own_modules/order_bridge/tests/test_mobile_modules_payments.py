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

    def _auth_headers(self, key=None):
        return {
            'Accept': 'application/json',
            'X-Api-Key': key if key is not None else self.api_key,
        }

    def _json_headers(self, key=None):
        headers = self._auth_headers(key)
        headers['Content-Type'] = 'application/json'
        return headers

    def _create_due_order(self, *, phone='+5353024637', price=100.0, qty=1.0):
        key = phone_match_key(phone)
        partner = self.env['res.partner'].search([
            ('order_bridge_phone_key', '=', key),
            ('company_id', 'in', [False, self.env.company.id]),
        ], limit=1) if key else self.env['res.partner']
        if not partner:
            partner = self.env['res.partner'].create({
                'name': f'Cliente {phone}',
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
            self.assertEqual(json.loads(res.text), {'error': error}, body)

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
        self.assertEqual(json.loads(res.text), {'result': 'not_interested'})

        transfer = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM-NOT-INTERESTED'),
            ('transfer_type', '=', 'mobile'),
        ])
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.result, 'not_interested')
        self.assertFalse(transfer.payment_ids)

        # Idempotent replay
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
        self.assertEqual(json.loads(res2.text), {'result': 'not_interested'})
        self.assertEqual(
            self.env['order_bridge.transfer'].search_count([
                ('code', '=', 'MM-NOT-INTERESTED'),
            ]),
            1,
        )

    def test_post_payments_processed_applies_to_due_orders(self):
        partner, order1 = self._create_due_order(phone='+5353024637', price=60.0)
        _partner2, order2 = self._create_due_order(phone='53024637', price=40.0)
        self.assertEqual(partner, order2.partner_id)
        self.assertEqual(order1.order_bridge_amount_due, 60.0)
        self.assertEqual(order2.order_bridge_amount_due, 40.0)

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '53024637',
                'amount': 100,
                'code': 'MM604IQZC0987',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(json.loads(res.text), {'result': 'processed'})

        order1.invalidate_recordset()
        order2.invalidate_recordset()
        self.assertEqual(order1.order_bridge_amount_due, 0.0)
        self.assertEqual(order2.order_bridge_amount_due, 0.0)

        transfer = self.env['order_bridge.transfer'].search([
            ('code', '=', 'MM604IQZC0987'),
        ])
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.result, 'processed')
        self.assertEqual(len(transfer.payment_ids), 2)
        self.assertEqual(sum(transfer.payment_ids.mapped('amount')), 100.0)
        self.assertTrue(all(
            p.method_id == self.transfer for p in transfer.payment_ids
        ))

        # Idempotent: same code does not pay again
        res2 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5353024637',
                'amount': 100,
                'code': 'MM604IQZC0987',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self.assertEqual(json.loads(res2.text), {'result': 'processed'})
        self.assertEqual(
            self.env['order_bridge.order.payment'].search_count([
                ('transfer_id', '=', transfer.id),
            ]),
            2,
        )

    def test_post_payments_partial_across_orders(self):
        partner, order1 = self._create_due_order(phone='+5358330830', price=80.0)
        _, order2 = self._create_due_order(phone='58330830', price=50.0)
        self.assertEqual(partner, order2.partner_id)

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5358330830',
                'amount': 100,
                'code': 'PARTIAL-100',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(json.loads(res.text), {'result': 'processed'})

        order1.invalidate_recordset()
        order2.invalidate_recordset()
        self.assertEqual(order1.order_bridge_amount_due, 0.0)
        self.assertEqual(order2.order_bridge_amount_due, 30.0)

    def test_deliveries_require_delivery_module(self):
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(self.no_modules.api_key),
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)
