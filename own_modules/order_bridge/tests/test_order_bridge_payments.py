# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.float_utils import float_compare


@tagged('post_install', '-at_install')
class TestOrderBridgePayments(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente cobros test',
            'phone': '+529991110001',
        })
        self.cash = self.env.ref('order_bridge.payment_method_cash')
        self.transfer = self.env.ref('order_bridge.payment_method_transfer')
        tmpl = self.env['product.template'].create({
            'name': 'Producto cobros test',
            'sale_ok': True,
            'list_price': 100.0,
            'taxes_id': [Command.clear()],
        })
        self.product = tmpl.product_variant_id
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
                'tax_ids': [Command.clear()],
            })],
        })

    def test_empty_order_is_fully_paid(self):
        self.assertFalse(self.order.order_bridge_payment_ids)
        self.assertFalse(self.order.order_bridge_payment_pending)
        self.assertEqual(self.order.order_bridge_amount_paid, 0.0)
        self.assertEqual(self.order.order_bridge_amount_due, 0.0)
        self.assertEqual(self.partner.order_bridge_amount_due, 0.0)

    def test_payment_pending_without_lines_means_full_due(self):
        self.order.order_bridge_payment_pending = True
        self.assertEqual(self.order.order_bridge_amount_paid, 0.0)
        self.assertEqual(self.order.order_bridge_amount_due, self.order.amount_total)
        self.assertEqual(self.partner.order_bridge_amount_due, self.order.amount_total)

        due_partners = self.env['res.partner'].search([
            ('order_bridge_amount_due', '>', 0),
            ('id', '=', self.partner.id),
        ])
        self.assertIn(self.partner, due_partners)

    def test_mixed_partial_payments(self):
        self.order.write({
            'order_bridge_payment_ids': [
                Command.create({
                    'method_id': self.cash.id,
                    'amount': 40.0,
                }),
                Command.create({
                    'method_id': self.transfer.id,
                    'amount': 25.0,
                }),
            ],
        })
        self.assertEqual(self.order.order_bridge_amount_paid, 65.0)
        self.assertEqual(self.order.order_bridge_amount_due, 35.0)
        self.assertEqual(self.partner.order_bridge_amount_due, 35.0)

        due_orders = self.env['sale.order'].search([
            ('order_bridge_amount_due', '>', 0),
            ('id', '=', self.order.id),
        ])
        self.assertIn(self.order, due_orders)

    def test_payments_covering_total_clear_due(self):
        self.order.write({
            'order_bridge_payment_pending': True,
            'order_bridge_payment_ids': [
                Command.create({
                    'method_id': self.cash.id,
                    'amount': 60.0,
                }),
                Command.create({
                    'method_id': self.transfer.id,
                    'amount': 40.0,
                }),
            ],
        })
        self.assertEqual(self.order.order_bridge_amount_paid, 100.0)
        self.assertEqual(self.order.order_bridge_amount_due, 0.0)
        self.assertEqual(self.partner.order_bridge_amount_due, 0.0)

        due_orders = self.env['sale.order'].search([
            ('order_bridge_amount_due', '>', 0),
            ('id', '=', self.order.id),
        ])
        self.assertNotIn(self.order, due_orders)

    def test_payments_cannot_exceed_total(self):
        with self.assertRaises(UserError):
            self.order.write({
                'order_bridge_payment_ids': [
                    Command.create({
                        'method_id': self.cash.id,
                        'amount': 70.0,
                    }),
                    Command.create({
                        'method_id': self.transfer.id,
                        'amount': 40.0,
                    }),
                ],
            })

    def test_canceled_order_has_zero_due(self):
        self.order.write({
            'order_bridge_payment_pending': True,
            'order_bridge_payment_ids': [
                Command.create({
                    'method_id': self.cash.id,
                    'amount': 30.0,
                }),
            ],
        })
        self.assertTrue(
            float_compare(self.order.order_bridge_amount_due, 0.0, precision_digits=2) > 0
        )
        self.order.action_order_bridge_cancel_store()
        self.assertEqual(self.order.order_bridge_store_state, 'canceled')
        self.assertEqual(self.order.order_bridge_amount_due, 0.0)
        self.assertEqual(self.partner.order_bridge_amount_due, 0.0)

        with self.assertRaises(UserError):
            self.env['order_bridge.order.payment'].create({
                'order_id': self.order.id,
                'method_id': self.cash.id,
                'amount': 10.0,
            })

    def test_open_orders_with_due_action(self):
        self.order.order_bridge_payment_pending = True
        action = self.partner.action_open_order_bridge_orders_with_due()
        matched = self.env['sale.order'].search(action['domain'])
        self.assertIn(self.order, matched)

    def test_ui_transfer_create_registers_without_applying(self):
        self.order.order_bridge_payment_pending = True
        due_before = self.order.order_bridge_amount_due

        transfer = self.env['order_bridge.transfer'].create({
            'phone': self.partner.phone,
            'amount': self.order.amount_total,
            'code': 'UI-MANUAL-001',
        })
        self.assertEqual(transfer.result, 'processed')
        self.assertFalse(transfer.applied)
        self.assertFalse(transfer.payment_ids)
        self.assertFalse(transfer.partner_id)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.order_bridge_amount_due, due_before)

        with self.assertRaises(UserError):
            self.env['order_bridge.transfer'].create({
                'phone': self.partner.phone,
                'amount': 10.0,
                'code': 'UI-MANUAL-001',
            })

    def test_ui_transfer_apply_to_debt(self):
        self.order.order_bridge_payment_pending = True
        transfer = self.env['order_bridge.transfer'].create({
            'phone': '+529998887776',
            'amount': 60.0,
            'code': 'UI-APPLY-001',
        })
        with self.assertRaises(UserError):
            transfer.action_apply_to_debt()

        transfer.partner_id = self.partner
        transfer.action_apply_to_debt()
        self.assertTrue(transfer.applied)
        self.assertEqual(len(transfer.payment_ids), 1)
        self.assertEqual(transfer.payment_ids.amount, 60.0)
        self.assertEqual(transfer.payment_ids.method_id, self.transfer)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.order_bridge_amount_due, 40.0)

        with self.assertRaises(UserError):
            transfer.action_apply_to_debt()
        with self.assertRaises(UserError):
            transfer.partner_id = False

    def test_ui_transfer_apply_without_debt(self):
        transfer = self.env['order_bridge.transfer'].create({
            'phone': '+529998887775',
            'amount': 50.0,
            'code': 'UI-APPLY-NO-DEBT',
            'partner_id': self.partner.id,
        })
        with self.assertRaises(UserError):
            transfer.action_apply_to_debt()
        self.assertFalse(transfer.payment_ids)

    def test_ui_transfer_apply_partial_across_orders(self):
        self.order.order_bridge_payment_pending = True
        order2 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_bridge_origin': 'admin',
            'order_bridge_payment_pending': True,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 50.0,
                'tax_ids': [Command.clear()],
            })],
        })
        transfer = self.env['order_bridge.transfer'].create({
            'phone': '9991110001',
            'amount': 120.0,
            'code': 'UI-APPLY-PARTIAL',
            'partner_id': self.partner.id,
        })
        transfer.action_apply_to_debt()
        self.assertEqual(len(transfer.payment_ids), 2)
        self.assertEqual(sum(transfer.payment_ids.mapped('amount')), 120.0)
        self.order.invalidate_recordset()
        order2.invalidate_recordset()
        self.assertEqual(self.order.order_bridge_amount_due, 0.0)
        self.assertEqual(order2.order_bridge_amount_due, 30.0)
