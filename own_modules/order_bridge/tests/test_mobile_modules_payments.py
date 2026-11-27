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

    def test_post_payments_invalid_order_identifier_400(self):
        for bad_id in ('', '   ', 123, True, [], {}):
            res = self.url_open(
                '/api/mobile/v1/payments',
                data=json.dumps({
                    'phone': '5359012010',
                    'amount': 20,
                    'code': 'MM-BAD-ORDER-ID',
                    'orderIdentifier': bad_id,
                }),
                headers=self._json_headers(),
                timeout=60,
            )
            self.assertEqual(res.status_code, 400, f'Expected 400 for {bad_id!r}: {res.text}')
            self.assertEqual(json.loads(res.text), {'error': 'invalid_order_identifier'})

    def test_post_payments_order_not_found_404(self):
        _, foreign_order = self._create_due_order(phone='+5359012011', price=100.0)
        foreign_order.write({'order_bridge_messenger_id': self.delivery_only.id})

        for identifier in ('999999999', 'SO-NO-NUM', str(foreign_order.id)):
            res = self.url_open(
                '/api/mobile/v1/payments',
                data=json.dumps({
                    'phone': '5359012011',
                    'amount': 20,
                    'code': 'MM-ORDER-404',
                    'orderIdentifier': identifier,
                }),
                headers=self._json_headers(),
                timeout=60,
            )
            self.assertEqual(res.status_code, 404, f'Expected 404 for {identifier}: {res.text}')
            self.assertEqual(json.loads(res.text), {'error': 'order_not_found'})

    def test_post_payments_link_order_idempotency_and_conflict(self):
        _, order1 = self._create_due_order(phone='+5359012012', price=100.0)
        _, order2 = self._create_due_order(phone='+5359012013', price=100.0)
        order1.write({
            'order_bridge_messenger_id': self.messenger.id,
            'order_bridge_store_state': 'ready_for_delivery',
        })
        order1.write({'order_bridge_store_state': 'delivered'})
        order2.write({
            'order_bridge_messenger_id': self.messenger.id,
            'order_bridge_store_state': 'ready_for_delivery',
        })

        # 1. First consult without orderIdentifier
        res1 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012012',
                'amount': 60,
                'code': 'MM-LINK-FLOW-1',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res1.status_code, 200, res1.text)
        self._assert_payment_ok(json.loads(res1.text), result='processed', backend_equals='')

        # 2. Re-send same code WITH orderIdentifier (already delivered order) -> links now
        res2 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012012',
                'amount': 60,
                'code': 'MM-LINK-FLOW-1',
                'orderIdentifier': str(order1.id),
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        data2 = json.loads(res2.text)
        self.assertEqual(data2['result'], 'processed')
        self.assertIn(order1.name, data2['backendResponse'])

        transfer = self.env['order_bridge.transfer'].search([('code', '=', 'MM-LINK-FLOW-1')])
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.payment_ids.mapped('order_id'), order1)
        self.assertEqual(len(transfer.payment_ids), 1)
        self.assertAlmostEqual(transfer.payment_ids.amount, 60.0, places=2)
        order1.invalidate_recordset()
        self.assertAlmostEqual(order1.order_bridge_amount_due, 40.0, places=2)

        # 3. Repeat same code + same orderIdentifier -> idempotent, no duplicate payment
        res3 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5300000000',
                'amount': 999,
                'code': 'MM-LINK-FLOW-1',
                'orderIdentifier': str(order1.id),
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res3.status_code, 200, res3.text)
        self.assertEqual(json.loads(res3.text), data2)
        transfer.invalidate_recordset()
        self.assertEqual(len(transfer.payment_ids), 1)

        # 4. Repeat without orderIdentifier -> does NOT touch payments
        res4 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012012',
                'amount': 60,
                'code': 'MM-LINK-FLOW-1',
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res4.status_code, 200, res4.text)
        transfer.invalidate_recordset()
        self.assertEqual(transfer.payment_ids.mapped('order_id'), order1)

        # 5. Repeat with different orderIdentifier when balance is exhausted -> 409 conflict
        res5 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012013',
                'amount': 60,
                'code': 'MM-LINK-FLOW-1',
                'orderIdentifier': str(order2.id),
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res5.status_code, 409, res5.text)
        self.assertEqual(json.loads(res5.text), {'error': 'transfer_linked_to_other_order'})

    def test_post_payments_backend_applied_to_other_order_returns_409(self):
        partner1, order1 = self._create_due_order(phone='+5359012020', price=100.0)
        _, order2 = self._create_due_order(phone='+5359012021', price=100.0)
        order2.write({
            'order_bridge_messenger_id': self.messenger.id,
            'order_bridge_store_state': 'ready_for_delivery',
        })

        transfer = self.env['order_bridge.transfer'].create({
            'phone': '5359012020',
            'amount': 80.0,
            'code': 'MM-BACKEND-USED-1',
            'partner_id': partner1.id,
        })
        transfer.action_apply_to_debt()
        self.assertEqual(transfer.payment_ids.mapped('order_id'), order1)

        res = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012021',
                'amount': 80,
                'code': 'MM-BACKEND-USED-1',
                'orderIdentifier': str(order2.id),
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(json.loads(res.text), {'error': 'transfer_linked_to_other_order'})
        transfer.invalidate_recordset()
        self.assertEqual(transfer.payment_ids.mapped('order_id'), order1)

    def test_post_payments_partial_balance_applies_remaining_then_rejects(self):
        partner1, order1 = self._create_due_order(phone='+5359012022', price=80.0)
        _, order2 = self._create_due_order(phone='+5359012023', price=100.0)
        _, order3 = self._create_due_order(phone='+5359012024', price=50.0)
        order2.write({
            'order_bridge_messenger_id': self.messenger.id,
            'order_bridge_store_state': 'ready_for_delivery',
        })
        order3.write({
            'order_bridge_messenger_id': self.messenger.id,
            'order_bridge_store_state': 'ready_for_delivery',
        })

        transfer = self.env['order_bridge.transfer'].create({
            'phone': '5359012022',
            'amount': 120.0,
            'code': 'MM-PARTIAL-BAL-1',
            'partner_id': partner1.id,
        })
        transfer.action_apply_to_debt()
        self.assertEqual(len(transfer.payment_ids), 1)
        self.assertAlmostEqual(transfer.payment_ids.amount, 80.0, places=2)

        # Free balance is 40 -> order2 gets a payment of 40
        res2 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012023',
                'amount': 120,
                'code': 'MM-PARTIAL-BAL-1',
                'orderIdentifier': str(order2.id),
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self.assertEqual(json.loads(res2.text)['result'], 'processed')
        transfer.invalidate_recordset()
        order2.invalidate_recordset()
        self.assertEqual(len(transfer.payment_ids), 2)
        p2 = transfer.payment_ids.filtered(lambda p: p.order_id == order2)
        self.assertAlmostEqual(p2.amount, 40.0, places=2)
        self.assertAlmostEqual(order2.order_bridge_amount_due, 60.0, places=2)

        # Free balance is now 0 -> order3 is rejected with 409
        res3 = self.url_open(
            '/api/mobile/v1/payments',
            data=json.dumps({
                'phone': '5359012024',
                'amount': 120,
                'code': 'MM-PARTIAL-BAL-1',
                'orderIdentifier': str(order3.id),
            }),
            headers=self._json_headers(),
            timeout=60,
        )
        self.assertEqual(res3.status_code, 409, res3.text)
        self.assertEqual(json.loads(res3.text), {'error': 'transfer_linked_to_other_order'})
        transfer.invalidate_recordset()
        self.assertEqual(len(transfer.payment_ids), 2)
