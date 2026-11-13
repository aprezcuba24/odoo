# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPaymentMethodStripe(TransactionCase):
    def setUp(self):
        super().setUp()
        self.stripe = self.env.ref('payment_gateway.payment_method_stripe')
        self.cash = self.env.ref('order_bridge.payment_method_cash')
        self.transfer = self.env.ref('order_bridge.payment_method_transfer')
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente Stripe vía test',
            'phone': '+529991110099',
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto Stripe vía test',
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

    def test_stripe_method_exists_on_order_bridge_model(self):
        self.assertEqual(self.stripe._name, 'order_bridge.payment.method')
        self.assertEqual(self.stripe.name, 'Stripe')
        self.assertEqual(self.stripe.sequence, 30)
        self.assertTrue(self.stripe.active)

    def test_cash_and_transfer_remain_on_order_bridge(self):
        self.assertEqual(self.cash.name, 'Efectivo')
        self.assertEqual(self.transfer.name, 'Transferencia')
        self.assertTrue(self.cash.exists())
        self.assertTrue(self.transfer.exists())

    def test_stripe_payment_line_updates_order_balance(self):
        self.assertEqual(self.order.order_bridge_amount_due, 0.0)

        self.order.write({
            'order_bridge_payment_pending': True,
            'order_bridge_payment_ids': [
                Command.create({
                    'method_id': self.stripe.id,
                    'amount': 40.0,
                }),
            ],
        })
        payment = self.order.order_bridge_payment_ids
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment.method_id, self.stripe)
        self.assertEqual(self.order.order_bridge_amount_paid, 40.0)
        self.assertEqual(self.order.order_bridge_amount_due, 60.0)
